"""
DataGhost – Comprehensive Multi-Device Management & Enrollment Routes.

Routes:
  GET    /devices                      – List all devices with dynamic online/offline status
  POST   /devices/enrollment/create    – Generate secure enrollment token & QR code data (Admin/Analyst)
  GET    /devices/enrollment/status/{c}– Query status of an enrollment session (polling)
  POST   /devices/enrollment/register  – Register an endpoint using enrollment token/code
  POST   /devices/{id}/heartbeat       – Receive agent heartbeat & update status/counters
  POST   /devices/heartbeat            – Fallback heartbeat route with device_id in body
  GET    /devices/{id}                 – Get detailed device info, security metrics & activity
  PATCH  /devices/{id}                 – Update device metadata / enable / disable
  DELETE /devices/{id}                 – Remove a device
  POST   /devices/register             – Legacy agent registration endpoint
"""
import hashlib
import json
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import desc
from sqlalchemy.orm import Session

from auth import get_current_user, require_admin
from config import settings
from database import get_db
from models import Device, EnrollmentToken, Incident, ScanLog, User
from schemas.schemas import (
    DeviceDetailResponse,
    DeviceHeartbeatRequest,
    DeviceHeartbeatResponse,
    DeviceRegisterRequest,
    DeviceResponse,
    DeviceUpdateRequest,
    DeviceScanTriggerRequest,
    EnrollmentCreateRequest,
    EnrollmentCreateResponse,
    EnrollmentRegisterRequest,
    EnrollmentRegisterResponse,
    EnrollmentStatusResponse,
    IncidentResponse,
)

logger = logging.getLogger("dataghost.devices")

router = APIRouter(prefix="/devices", tags=["devices"])


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _compute_device_status(device: Device, timeout_seconds: int) -> str:
    """Return ACTIVE, OFFLINE, or DISABLED based on last_seen and heartbeat timeout."""
    if device.status == "DISABLED":
        return "DISABLED"
    if not device.last_seen:
        return "OFFLINE"
    now = _utc_now()
    last = device.last_seen
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    if (now - last).total_seconds() > timeout_seconds:
        return "OFFLINE"
    return "ACTIVE"


def _normalize_platform(raw: Optional[str]) -> str:
    """Normalize OS/platform identifiers."""
    if not raw:
        return "Windows"
    raw_lower = raw.lower()
    if "win" in raw_lower:
        return "Windows"
    if "linux" in raw_lower:
        return "Linux"
    if "mac" in raw_lower or "darwin" in raw_lower:
        return "macOS"
    if "android" in raw_lower:
        return "Android"
    if "ios" in raw_lower or "iphone" in raw_lower or "ipad" in raw_lower:
        return "iOS"
    return raw.capitalize()


def _find_device(identifier: str, db: Session) -> Optional[Device]:
    """Find device by unique device_id or primary key id."""
    device = db.query(Device).filter(Device.device_id == identifier).first()
    if device:
        return device
    if identifier.isdigit():
        return db.query(Device).filter(Device.id == int(identifier)).first()
    return None


def _sync_to_firebase(device: Device):
    """Safely sync device details to Firebase Firestore if enabled."""
    try:
        from firebase_db import sync_device_to_firestore
        sync_device_to_firestore({
            "device_id": device.device_id,
            "device_name": device.device_name,
            "platform": device.platform,
            "ip_address": device.ip_address,
            "os_type": device.os_type or device.platform,
            "agent_version": device.agent_version,
            "status": device.status,
            "files_scanned": device.files_scanned or 0,
            "incidents_count": device.incidents_count or 0,
            "last_seen": device.last_seen.isoformat() if device.last_seen else None,
            "enrolled_at": device.enrolled_at.isoformat() if device.enrolled_at else None,
        })
    except Exception as exc:
        logger.debug("Firebase sync skipped: %s", exc)


# ---------------------------------------------------------------------------
# 1. Device List (Dynamic status calculation)
# ---------------------------------------------------------------------------
@router.get("", response_model=list[DeviceResponse])
def list_devices(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return registered devices with real-time status.

    RBAC:
      admin   → all devices in the system.
      analyst → only devices belonging to 'default-org'.
    """
    timeout = getattr(settings, "DEVICE_HEARTBEAT_TIMEOUT_SECONDS", 120)

    if current_user.role == "admin":
        devices = db.query(Device).order_by(Device.device_name).all()
    else:
        devices = (
            db.query(Device)
            .filter(Device.organization_id == "default-org")
            .order_by(Device.device_name)
            .all()
        )

    # Recompute status dynamically without forcing full db commit on reads
    for dev in devices:
        computed = _compute_device_status(dev, timeout)
        if dev.status != computed and dev.status != "DISABLED":
            dev.status = computed

    return devices


# ---------------------------------------------------------------------------
# 2. Enrollment Token Creation & QR Generation
# ---------------------------------------------------------------------------
@router.post("/enrollment/create", response_model=EnrollmentCreateResponse)
def create_enrollment_token(
    payload: EnrollmentCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a secure, one-time enrollment token with expiration and QR code data.
    Only authenticated administrators/analysts can generate enrollment codes.
    """
    norm_platform = _normalize_platform(payload.platform)
    valid_platforms = {"Windows", "Linux", "macOS", "Android", "iOS"}
    if norm_platform not in valid_platforms:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid platform '{payload.platform}'. Supported: {', '.join(sorted(valid_platforms))}",
        )

    # Cryptographically random token (32 URL-safe bytes = 43 chars)
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    # Human-friendly readable code: DG-XXXX-XXXX
    enrollment_code = f"DG-{secrets.token_hex(2).upper()}-{secrets.token_hex(2).upper()}"

    expire_minutes = getattr(settings, "ENROLLMENT_TOKEN_EXPIRE_MINUTES", 10)
    expires_at = _utc_now() + timedelta(minutes=expire_minutes)

    enrollment = EnrollmentToken(
        token_hash=token_hash,
        enrollment_code=enrollment_code,
        platform=norm_platform,
        organization_id=payload.organization_id,
        created_by=current_user.username,
        expires_at=expires_at,
        status="PENDING",
    )
    db.add(enrollment)
    db.commit()
    db.refresh(enrollment)

    # Server URL for device connection
    server_url = getattr(settings, "SERVER_PUBLIC_URL", "http://localhost:8000")

    # Minimal, secure QR code data payload
    qr_payload = {
        "version": "1.0",
        "server_url": server_url,
        "token": raw_token,
        "code": enrollment_code,
        "platform": norm_platform,
        "expires_at": expires_at.isoformat(),
    }

    return EnrollmentCreateResponse(
        enrollment_code=enrollment_code,
        raw_token=raw_token,
        platform=norm_platform,
        qr_data=json.dumps(qr_payload),
        server_url=server_url,
        expires_at=expires_at,
        expires_in_seconds=int(expire_minutes * 60),
        status="PENDING",
    )


# ---------------------------------------------------------------------------
# 2b. Easy / Direct Enrollment QR  (URL-based, no factory reset required)
# ---------------------------------------------------------------------------
@router.post("/enrollment/create-easy", response_model=EnrollmentCreateResponse)
def create_easy_enrollment(
    payload: EnrollmentCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generate an Easy Enrollment QR code — a plain HTTPS URL the device
    opens in a browser to download and install the DataGhost Agent.

    HOW IT WORKS:
      1. Admin generates this QR code in the DataGhost dashboard.
      2. User scans the QR with any camera app on Android / desktop / mobile.
      3. Device opens: {SERVER_PUBLIC_URL}/enroll/{enrollment_code}
      4. The enrollment page auto-detects the OS and shows the correct
         download link + instructions.
      5. User downloads & installs the DataGhost Agent.
      6. Agent opens with the enrollment code pre-filled (via deep link).
      7. Agent calls POST /api/devices/enrollment/register.
      8. Device appears in the Devices dashboard.

    SUPPORTS: Android (Agent-managed), Windows, Linux.
    DOES NOT REQUIRE: factory reset, Android Enterprise provisioning,
                      separate QR scanner app, or Device Owner mode.

    The QR payload is a plain HTTPS URL — NOT an Android Enterprise
    provisioning payload. The URL contains ONLY the enrollment code.
    No tokens, secrets, or provisioning credentials are embedded.
    """
    norm_platform = _normalize_platform(payload.platform)
    valid_platforms = {"Windows", "Linux", "macOS", "Android", "iOS"}
    if norm_platform not in valid_platforms:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid platform '{payload.platform}'. Supported: {', '.join(sorted(valid_platforms))}",
        )

    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    # Human-readable DG-XXXX-XXXX code for consistency across all platforms
    enrollment_code = f"DG-{secrets.token_hex(2).upper()}-{secrets.token_hex(2).upper()}"

    expire_minutes = getattr(settings, "ENROLLMENT_TOKEN_EXPIRE_MINUTES", 10)
    expires_at = _utc_now() + timedelta(minutes=expire_minutes)

    enrollment = EnrollmentToken(
        token_hash=token_hash,
        enrollment_code=enrollment_code,
        platform=norm_platform,
        organization_id=payload.organization_id or "default-org",
        created_by=current_user.username,
        expires_at=expires_at,
        status="PENDING",
    )
    db.add(enrollment)
    db.commit()
    db.refresh(enrollment)

    server_url = getattr(settings, "SERVER_PUBLIC_URL", "http://localhost:3000")

    # QR data is a plain HTTPS URL — no secrets embedded.
    # The enrollment code alone is the credential; the raw token stays
    # server-side and is verified when the agent calls /register.
    qr_url = f"{server_url}/enroll/{enrollment_code}"

    return EnrollmentCreateResponse(
        enrollment_code=enrollment_code,
        raw_token=raw_token,
        platform=norm_platform,
        qr_data=qr_url,          # Plain URL — camera-friendly
        server_url=server_url,
        expires_at=expires_at,
        expires_in_seconds=int(expire_minutes * 60),
        status="PENDING",
    )


# ---------------------------------------------------------------------------
# 2c. Android Enterprise Enrollment QR (DPC/EMM-compatible payload)
# ---------------------------------------------------------------------------
@router.post("/enrollment/create-android-enterprise", response_model=EnrollmentCreateResponse)
def create_android_enterprise_enrollment(
    payload: EnrollmentCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generate an Android Enterprise-compatible enrollment QR code payload.

    This is a CUSTOM DPC implementation (not Google AMAPI or Play EMM API).
    The QR data conforms to the Android Device Policy Controller (DPC) QR
    provisioning specification for custom DPCs:

      https://developer.android.com/work/dpc/build-dpc#qr_code

    HOW IT WORKS (Fully Managed / Device Owner):
      1. Admin generates this QR code in the DataGhost dashboard.
      2. A corporate Android device is factory-reset.
      3. During the setup wizard, user taps the screen 6x to trigger QR enrollment.
      4. Android scans this QR code.
      5. Android downloads the DataGhost Agent APK from PROVISIONING_DEVICE_ADMIN_PACKAGE_DOWNLOAD_LOCATION.
      6. Android verifies the APK against PROVISIONING_DEVICE_ADMIN_PACKAGE_CHECKSUM.
      7. Android installs the APK and makes DataGhostDeviceAdminReceiver the Device Owner.
      8. Android shows the user "This device is managed by [org]" consent screens.
         *** The user must acknowledge these screens. This is NOT a silent process. ***
      9. Android broadcasts PROFILE_PROVISIONING_COMPLETE to DataGhostDeviceAdminReceiver.
     10. The receiver calls POST /api/devices/enrollment/register.
     11. The device appears in the DataGhost Devices dashboard.

    REQUIREMENTS:
      - The DataGhost Agent APK must be hosted at a publicly accessible HTTPS URL.
      - The APK must be signed. PROVISIONING_DEVICE_ADMIN_PACKAGE_CHECKSUM is the
        SHA-256 hash of the APK's signing certificate (DER-encoded, then base64url-encoded).
        Generate with: keytool -list -v -keystore release.keystore | grep 'SHA256:'
        OR via script: apksigner verify --print-certs app.apk | grep 'Signer #1 certificate SHA-256'
      - PROVISIONING_DEVICE_ADMIN_PACKAGE_DOWNLOAD_LOCATION must serve the signed APK.
        In development, you can serve the debug APK via your dev tunnel:
        PUT the debug APK file at: {SERVER_PUBLIC_URL}/dataghost-agent.apk

    This does NOT use:
      - Android Management API (AMAPI) / Google EMM API
      - Zero-touch enrollment (requires Google Reseller or Zero-touch portal)
      - Google Play Store distribution
    """
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    enrollment_code = f"DG-{secrets.token_hex(2).upper()}-{secrets.token_hex(2).upper()}"

    expire_minutes = getattr(settings, "ENROLLMENT_TOKEN_EXPIRE_MINUTES", 10)
    expires_at = _utc_now() + timedelta(minutes=expire_minutes)

    enrollment = EnrollmentToken(
        token_hash=token_hash,
        enrollment_code=enrollment_code,
        platform="Android",
        organization_id=payload.organization_id or "default-org",
        created_by=current_user.username,
        expires_at=expires_at,
        status="PENDING",
    )
    db.add(enrollment)
    db.commit()
    db.refresh(enrollment)

    server_url = getattr(settings, "SERVER_PUBLIC_URL", "http://localhost:8000")

    # ── Android Enterprise DPC-compatible QR payload ─────────────────────────
    # Reference: https://developer.android.com/work/dpc/build-dpc#qr_code
    #
    # IMPORTANT: Before using in production you MUST:
    #   1. Build and sign the DataGhost Agent APK.
    #   2. Host the signed APK at an HTTPS URL.
    #   3. Set PROVISIONING_DEVICE_ADMIN_PACKAGE_CHECKSUM to the SHA-256
    #      hash of the APK signing certificate (base64url-encoded, no padding).
    #      Android REJECTS the QR if this is blank or incorrect.
    #   4. Set PROVISIONING_DEVICE_ADMIN_PACKAGE_DOWNLOAD_LOCATION to the APK URL.
    #
    # The PROVISIONING_ADMIN_EXTRAS_BUNDLE is DataGhost-specific and is passed
    # to DataGhostDeviceAdminReceiver.onProfileProvisioningComplete().
    # It is NOT passed to the browser/mobile QR scanner in any unsafe way.
    # The raw_token is a one-time-use credential; it is single-use and
    # consumed the moment the device calls /enrollment/register.
    # ─────────────────────────────────────────────────────────────────────────

    # APK signing certificate SHA-256 hash (base64url, no padding).
    # PLACEHOLDER: replace with real value from your signed release APK.
    # Generate: apksigner verify --print-certs app-release.apk | grep 'SHA-256'
    # Then base64url-encode the hex bytes (without colons).
    apk_cert_checksum = getattr(
        settings, "ANDROID_DPC_CERT_CHECKSUM",
        "REPLACE_WITH_APK_SIGNING_CERT_SHA256_BASE64URL"
    )

    android_enterprise_qr = {
        # Standard DataGhost fields (for the DataGhost Agent app parser / Work Profile path)
        "version": "1.0",
        "server_url": server_url,
        "token": raw_token,
        "code": enrollment_code,
        "platform": "Android",
        "expires_at": expires_at.isoformat(),

        # ── Android Enterprise DPC provisioning fields ─────────────────────
        # The DPC component that handles enrollment as Device Owner
        "android.app.extra.PROVISIONING_DEVICE_ADMIN_COMPONENT_NAME":
            "com.dataghost.agent/com.dataghost.agent.enrollment.DataGhostDeviceAdminReceiver",

        # Where Android downloads the DPC APK during setup wizard
        # Must be an HTTPS URL serving the signed release APK
        "android.app.extra.PROVISIONING_DEVICE_ADMIN_PACKAGE_DOWNLOAD_LOCATION":
            f"{server_url}/dataghost-agent.apk",

        # SHA-256 hash of the APK signing certificate (base64url, no padding).
        # Android verifies this before installing. REQUIRED — cannot be blank.
        "android.app.extra.PROVISIONING_DEVICE_ADMIN_SIGNATURE_CHECKSUM": apk_cert_checksum,

        # Do not skip device encryption
        "android.app.extra.PROVISIONING_SKIP_ENCRYPTION": False,

        # DataGhost-specific extras passed into the DPC during provisioning.
        # Contains the enrollment token to call /api/devices/enrollment/register.
        # Google Service Account credentials are NOT included here.
        "android.app.extra.PROVISIONING_ADMIN_EXTRAS_BUNDLE": {
            "com.dataghost.SERVER_URL": server_url,
            "com.dataghost.ENROLLMENT_TOKEN": raw_token,
            "com.dataghost.ENROLLMENT_CODE": enrollment_code,
            "com.dataghost.EXPIRES_AT": expires_at.isoformat(),
        },
    }

    return EnrollmentCreateResponse(
        enrollment_code=enrollment_code,
        raw_token=raw_token,
        platform="Android",
        qr_data=json.dumps(android_enterprise_qr),
        server_url=server_url,
        expires_at=expires_at,
        expires_in_seconds=int(expire_minutes * 60),
        status="PENDING",
    )


# ---------------------------------------------------------------------------
# 3. Enrollment Status Polling
# ---------------------------------------------------------------------------
@router.get("/enrollment/status/{code_or_token}", response_model=EnrollmentStatusResponse)
def get_enrollment_status(
    code_or_token: str,
    db: Session = Depends(get_db),
):
    """
    Check the current status of an enrollment token/code.
    Used by the dashboard modal to detect when device successfully connects.
    """
    token_hash = hashlib.sha256(code_or_token.encode("utf-8")).hexdigest()
    enrollment = (
        db.query(EnrollmentToken)
        .filter(
            (EnrollmentToken.enrollment_code == code_or_token.upper())
            | (EnrollmentToken.token_hash == token_hash)
        )
        .first()
    )

    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Enrollment code or token not found.",
        )

    now = _utc_now()
    exp = enrollment.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)

    is_expired = now > exp
    if is_expired and enrollment.status == "PENDING":
        enrollment.status = "EXPIRED"
        db.commit()

    device_name = None
    if enrollment.device_id:
        dev = db.query(Device).filter(Device.device_id == enrollment.device_id).first()
        if dev:
            device_name = dev.device_name

    return EnrollmentStatusResponse(
        enrollment_code=enrollment.enrollment_code,
        platform=enrollment.platform,
        status=enrollment.status,
        device_id=enrollment.device_id,
        device_name=device_name,
        used_at=enrollment.used_at,
        expires_at=enrollment.expires_at,
        is_expired=is_expired,
    )


# ---------------------------------------------------------------------------
# 4. Device Registration with Enrollment Token
# ---------------------------------------------------------------------------
@router.post("/enrollment/register", response_model=EnrollmentRegisterResponse)
def register_with_enrollment(
    payload: EnrollmentRegisterRequest,
    db: Session = Depends(get_db),
):
    """
    Called by an endpoint agent (Windows, Linux, macOS, Android, iOS) during enrollment.
    Validates token, ensures single-use, assigns permanent device ID, and activates device.
    """
    enrollment = None

    if payload.token:
        token_hash = hashlib.sha256(payload.token.encode("utf-8")).hexdigest()
        enrollment = db.query(EnrollmentToken).filter(EnrollmentToken.token_hash == token_hash).first()

    if not enrollment and payload.enrollment_code:
        code_clean = payload.enrollment_code.strip().upper()
        enrollment = db.query(EnrollmentToken).filter(EnrollmentToken.enrollment_code == code_clean).first()

    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid enrollment credentials. Token or code not recognized.",
        )

    now = _utc_now()
    exp = enrollment.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)

    if enrollment.status != "PENDING":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Enrollment token is no longer valid (status: {enrollment.status}).",
        )

    if now > exp:
        enrollment.status = "EXPIRED"
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Enrollment code has expired. Please generate a new enrollment code.",
        )

    # Determine platform
    platform = enrollment.platform
    if payload.platform:
        client_platform = _normalize_platform(payload.platform)
        if client_platform == platform or platform in ("Windows", "Linux", "macOS"):
            platform = client_platform

    # Generate permanent, non-sequential unique device ID
    prefix_map = {
        "Windows": "dg-win",
        "Linux": "dg-linux",
        "macOS": "dg-mac",
        "Android": "dg-android",
        "iOS": "dg-ios",
    }
    pfx = prefix_map.get(platform, "dg-dev")

    # Generate unique ID
    new_device_id = ""
    for _ in range(5):
        cand = f"{pfx}-{secrets.token_hex(4)}"
        if not db.query(Device).filter(Device.device_id == cand).first():
            new_device_id = cand
            break

    if not new_device_id:
        new_device_id = f"{pfx}-{int(now.timestamp())}-{secrets.token_hex(2)}"

    device_name = payload.device_name.strip() or payload.hostname or f"DataGhost {platform} Device"

    # Create new Device
    device = Device(
        device_id=new_device_id,
        device_name=device_name,
        platform=platform,
        os_name=payload.os_name or platform,
        os_version=payload.os_version,
        architecture=payload.architecture,
        hostname=payload.hostname,
        ip_address=payload.ip_address,
        agent_version=payload.agent_version or "1.0.0",
        status="ACTIVE",
        last_seen=now,
        enrolled_at=now,
        registered_at=now,
        organization_id=enrollment.organization_id,
        os_type=platform,
        device_metadata=json.dumps(payload.device_metadata) if payload.device_metadata else None,
        files_scanned=0,
        incidents_count=0,
    )
    db.add(device)

    # Consume the enrollment token (one-time use)
    enrollment.status = "USED"
    enrollment.used_at = now
    enrollment.device_id = new_device_id

    db.commit()
    db.refresh(device)

    _sync_to_firebase(device)

    # Issue device auth token for future authenticated heartbeat/scanning
    device_token = f"dg_dev_{secrets.token_urlsafe(32)}"

    logger.info("Successfully enrolled device: %s (%s, %s)", new_device_id, device_name, platform)

    return EnrollmentRegisterResponse(
        device_id=device.device_id,
        device_name=device.device_name,
        platform=device.platform,
        status="ACTIVE",
        auth_token=device_token,
        heartbeat_interval_seconds=30,
        server_time=now,
        message="Device successfully enrolled and registered with DataGhost DLP.",
    )


# ---------------------------------------------------------------------------
# 5. Device Heartbeat
# ---------------------------------------------------------------------------
@router.post("/{device_id_or_id}/heartbeat", response_model=DeviceHeartbeatResponse)
def device_heartbeat_by_param(
    device_id_or_id: str,
    payload: Optional[DeviceHeartbeatRequest] = None,
    db: Session = Depends(get_db),
):
    """Handle periodic heartbeat from an enrolled agent using path parameter."""
    device = _find_device(device_id_or_id, db)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device '{device_id_or_id}' not found.",
        )

    now = _utc_now()
    device.last_seen = now
    if device.status != "DISABLED":
        device.status = "ACTIVE"

    if payload:
        if payload.agent_version:
            device.agent_version = payload.agent_version
        if payload.ip_address:
            device.ip_address = payload.ip_address
        if payload.files_scanned is not None and payload.files_scanned >= (device.files_scanned or 0):
            device.files_scanned = payload.files_scanned
        if payload.incidents_count is not None and payload.incidents_count >= (device.incidents_count or 0):
            device.incidents_count = payload.incidents_count
        if payload.device_metadata:
            device.device_metadata = json.dumps(payload.device_metadata)

    db.commit()
    db.refresh(device)
    _sync_to_firebase(device)

    return DeviceHeartbeatResponse(
        status="ok",
        device_id=device.device_id,
        last_seen=device.last_seen,
        policy_version="1.0",
        ack_timestamp=now,
    )


@router.post("/heartbeat", response_model=DeviceHeartbeatResponse)
def device_heartbeat_body(
    payload: DeviceHeartbeatRequest,
    db: Session = Depends(get_db),
):
    """Handle periodic heartbeat with device_id in request body."""
    return device_heartbeat_by_param(payload.device_id, payload, db)


# ---------------------------------------------------------------------------
# 6. Device Details (Device Information, Security, Activity)
# ---------------------------------------------------------------------------
@router.get("/{device_id_or_id}", response_model=DeviceDetailResponse)
def get_device_details(
    device_id_or_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieve comprehensive details for a specific device, including:
    - Core device specifications & metadata
    - Security stats (files scanned, incidents, last scan, last incident)
    - Recent security incidents
    """
    device = _find_device(device_id_or_id, db)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device '{device_id_or_id}' not found.",
        )

    if current_user.role != "admin" and device.organization_id != "default-org":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: You do not have permission to view details for this device.",
        )

    timeout = getattr(settings, "DEVICE_HEARTBEAT_TIMEOUT_SECONDS", 120)
    device.status = _compute_device_status(device, timeout)

    # Find last scan log
    last_scan_record = (
        db.query(ScanLog)
        .filter(ScanLog.device_id == device.device_id)
        .order_by(desc(ScanLog.timestamp))
        .first()
    )
    last_scan = last_scan_record.timestamp if last_scan_record else None

    # Find recent incidents
    recent_incidents_raw = (
        db.query(Incident)
        .filter(Incident.device_id == device.device_id)
        .order_by(desc(Incident.timestamp))
        .limit(10)
        .all()
    )

    last_incident = recent_incidents_raw[0].timestamp if recent_incidents_raw else None

    # Build response
    recent_incidents = []
    for inc in recent_incidents_raw:
        recent_incidents.append(
            IncidentResponse(
                id=inc.id,
                incident_id=inc.incident_id,
                timestamp=inc.timestamp,
                user=inc.user,
                filename=inc.filename,
                file_hash=inc.file_hash,
                classification=inc.classification,
                confidence=inc.confidence,
                risk_score=inc.risk_score,
                severity=inc.severity,
                recommended_action=inc.recommended_action,
                action_taken=inc.action_taken,
                destination=inc.destination,
                action=inc.action,
                status=inc.status,
                categories=[],
                triggered_rules=[],
                findings_json=inc.findings_json,
                device_id=inc.device_id,
                created_at=inc.created_at,
                updated_at=inc.updated_at,
            )
        )

    return DeviceDetailResponse(
        id=device.id,
        device_name=device.device_name,
        device_id=device.device_id,
        platform=device.platform or _normalize_platform(device.os_type),
        os_name=device.os_name,
        os_version=device.os_version,
        architecture=device.architecture,
        hostname=device.hostname,
        ip_address=device.ip_address,
        status=device.status,
        last_seen=device.last_seen,
        enrolled_at=device.enrolled_at,
        registered_at=device.registered_at,
        organization_id=device.organization_id,
        user_id=device.user_id,
        device_metadata=device.device_metadata,
        os_type=device.os_type,
        agent_version=device.agent_version,
        files_scanned=device.files_scanned or 0,
        incidents_count=device.incidents_count or 0,
        created_at=device.created_at,
        updated_at=device.updated_at,
        last_scan=last_scan,
        last_incident=last_incident,
        policy_status="Enforced" if device.status != "DISABLED" else "Disabled",
        recent_incidents=recent_incidents,
    )


# ---------------------------------------------------------------------------
# 7. Update Device (Enable / Disable / Rename)
# ---------------------------------------------------------------------------
@router.patch("/{device_id_or_id}", response_model=DeviceResponse)
def update_device(
    device_id_or_id: str,
    payload: DeviceUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Update device properties, such as re-enabling or disabling an endpoint (Admin only)."""
    device = _find_device(device_id_or_id, db)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device '{device_id_or_id}' not found.",
        )

    if payload.device_name is not None:
        device.device_name = payload.device_name.strip()
    if payload.status is not None:
        valid_statuses = {"ACTIVE", "DISABLED", "OFFLINE"}
        new_status = payload.status.upper()
        if new_status in valid_statuses:
            device.status = new_status
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status '{payload.status}'. Valid: {valid_statuses}",
            )
    if payload.ip_address is not None:
        device.ip_address = payload.ip_address

    db.commit()
    db.refresh(device)
    _sync_to_firebase(device)
    return device


# ---------------------------------------------------------------------------
# 8. Delete Device
# ---------------------------------------------------------------------------
@router.delete("/{device_id_or_id}")
def delete_device(
    device_id_or_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Remove a device record from management (Admin only)."""
    device = _find_device(device_id_or_id, db)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST if False else status.HTTP_404_NOT_FOUND,
            detail=f"Device '{device_id_or_id}' not found.",
        )

    dev_id = device.device_id
    dev_name = device.device_name

    db.delete(device)
    db.commit()

    logger.info("Device removed: %s (%s) by %s", dev_id, dev_name, current_user.username)
    return {
        "status": "deleted",
        "message": f"Device '{dev_name}' ({dev_id}) was successfully removed.",
        "device_id": dev_id,
    }


# ---------------------------------------------------------------------------
# 8b. Trigger Device Scan & Retrieve All Information
# ---------------------------------------------------------------------------
@router.post("/{device_id_or_id}/scan")
def trigger_device_scan(
    device_id_or_id: str,
    payload: Optional[DeviceScanTriggerRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Trigger a DLP security scan on the specified endpoint device.
    Dynamically scans real files from the host filesystem or custom endpoint payloads,
    evaluates sensitive findings via DLP regex patterns and the ML classifier,
    generates incidents, updates device telemetry, and returns comprehensive scan information.
    """
    device = _find_device(device_id_or_id, db)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device '{device_id_or_id}' not found.",
        )

    from api.scan_routes import _process_scan
    import os

    files_to_scan = []
    source_type = "live_filesystem"

    # Case 1: Custom text/payload provided by the client
    if payload and payload.custom_content:
        source_type = "custom_payload"
        files_to_scan.append({
            "filename": payload.filename or f"{device.device_name.lower().replace(' ', '_')}_active_scan.txt",
            "content": payload.custom_content.encode("utf-8"),
            "destination": (payload.destination or "EXTERNAL").upper(),
            "action": (payload.action or "UPLOAD").upper(),
            "classification": None,
        })
    # Case 2: Specific file path requested
    elif payload and payload.file_path:
        source_type = "live_filesystem"
        target_path = os.path.abspath(payload.file_path)
        if os.path.isfile(target_path):
            with open(target_path, "rb") as fh:
                raw_bytes = fh.read()
            files_to_scan.append({
                "filename": os.path.basename(target_path),
                "content": raw_bytes,
                "destination": (payload.destination or "EXTERNAL").upper(),
                "action": (payload.action or "UPLOAD").upper(),
                "classification": None,
            })
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Requested file path '{payload.file_path}' does not exist on disk.",
            )
    # Case 3: Dynamic filesystem discovery — scan all real files from the host OS
    else:
        import pathlib

        # Build a list of directories to scan based on the host OS
        scan_dirs: list[str] = []
        home = pathlib.Path.home()

        # User-content directories
        for subdir in ["Downloads", "Documents", "Desktop", "Pictures", "Music", "Videos"]:
            d = home / subdir
            if d.is_dir():
                scan_dirs.append(str(d))

        # Temp directories
        import tempfile
        scan_dirs.append(tempfile.gettempdir())

        # Workspace root (project directory)
        workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        scan_dirs.append(workspace_root)
        scan_dirs.append(str(home))

        # Scannable extensions (common document / data / config / source files)
        SCAN_EXTENSIONS = {
            ".txt", ".csv", ".json", ".xml", ".log", ".md",
            ".doc", ".docx", ".xls", ".xlsx", ".pdf",
            ".html", ".htm", ".env", ".ini", ".cfg", ".conf",
            ".yaml", ".yml", ".toml", ".sql", ".py", ".js", ".ts",
            ".pem", ".key", ".crt", ".db", ".bak",
        }

        # Directories to ignore during recursive walk (build caches, node_modules, etc.)
        IGNORED_DIRS = {
            ".git", "node_modules", ".venv", "venv", ".next", "__pycache__",
            "AppData", ".gemini", "dist", "build", "target", ".idea", ".vscode",
        }

        MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB per file cap
        max_files_limit = payload.max_files if (payload and payload.max_files is not None) else 1000
        if max_files_limit <= 0:
            max_files_limit = 10000

        seen_paths: set[str] = set()

        for scan_dir in scan_dirs:
            if max_files_limit > 0 and len(files_to_scan) >= max_files_limit:
                break
            try:
                base_path = pathlib.Path(scan_dir)
                if not base_path.exists():
                    continue

                # Walk directory tree
                for root, dirs, files in os.walk(str(base_path), topdown=True):
                    if max_files_limit > 0 and len(files_to_scan) >= max_files_limit:
                        break
                    # Prune ignored subdirectories in-place
                    dirs[:] = [d for d in dirs if d not in IGNORED_DIRS and not d.startswith(".")]

                    for fname in sorted(files):
                        if max_files_limit > 0 and len(files_to_scan) >= max_files_limit:
                            break
                        fpath = os.path.join(root, fname)
                        ext = os.path.splitext(fname)[1].lower()
                        if ext not in SCAN_EXTENSIONS:
                            continue

                        resolved = os.path.abspath(fpath)
                        if resolved in seen_paths:
                            continue
                        seen_paths.add(resolved)

                        try:
                            fsize = os.path.getsize(resolved)
                            if fsize == 0 or fsize > MAX_FILE_SIZE:
                                continue
                            with open(resolved, "rb") as fh:
                                raw_bytes = fh.read()

                            parent_lower = resolved.lower()
                            if "download" in parent_lower or "temp" in parent_lower:
                                dest, act = "EXTERNAL", "UPLOAD"
                            elif "desktop" in parent_lower or "document" in parent_lower:
                                dest, act = "LOCAL", "READ"
                            else:
                                dest, act = "INTERNAL", "COPY"

                            files_to_scan.append({
                                "filename": fname,
                                "content": raw_bytes,
                                "destination": dest,
                                "action": act,
                                "classification": None,
                            })
                        except (PermissionError, OSError) as read_err:
                            logger.debug("Skipping unreadable file %s: %s", resolved, read_err)
            except (PermissionError, OSError) as dir_err:
                logger.debug("Skipping inaccessible directory %s: %s", scan_dir, dir_err)

    if not files_to_scan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No scannable files discovered on host filesystem. "
                   "Ensure document files (.txt, .csv, .json, .pdf, etc.) exist in "
                   "the user's home, Downloads, Documents, or Desktop directories, "
                   "or provide a specific file_path or custom_content in the request body.",
        )

    results = []
    for item in files_to_scan:
        res = _process_scan(
            content=item["content"],
            filename=item["filename"],
            classification_override=item.get("classification"),
            destination=item["destination"],
            action=item["action"],
            file_size_override=len(item["content"]),
            device_id=device.device_id,
            user_label=current_user.username or "endpoint_user",
            db=db,
        )
        results.append(res)

    db.refresh(device)

    return {
        "status": "success",
        "message": f"Real-time scan completed successfully for device '{device.device_name}'.",
        "source": source_type,
        "device": {
            "device_id": device.device_id,
            "device_name": device.device_name,
            "platform": device.platform,
            "status": device.status,
            "files_scanned": device.files_scanned,
            "incidents_count": device.incidents_count,
            "last_seen": device.last_seen.isoformat() if device.last_seen else None,
            "os_name": device.os_name,
            "os_version": device.os_version,
            "hostname": device.hostname,
            "ip_address": device.ip_address,
        },
        "scanned_files_count": len(results),
        "threats_detected": sum(1 for r in results if r.risk_score >= 30),
        "high_risk_count": sum(1 for r in results if r.risk_score >= 70),
        "total_bytes_scanned": sum(len(item["content"]) for item in files_to_scan),
        "scan_results": [r.model_dump() for r in results],
    }


# ---------------------------------------------------------------------------
# 9. Legacy Device Registration (Backwards Compatibility)
# ---------------------------------------------------------------------------
@router.post("/register", response_model=DeviceResponse)
def register_device_legacy(
    payload: DeviceRegisterRequest,
    db: Session = Depends(get_db),
):
    """
    Legacy registration endpoint for backwards compatibility with existing agents.
    Upserts by device_id.
    """
    device = db.query(Device).filter(Device.device_id == payload.device_id).first()
    platform = payload.platform or _normalize_platform(payload.os_type)

    if device:
        device.device_name = payload.device_name
        device.ip_address = payload.ip_address
        device.os_type = payload.os_type or platform
        device.platform = platform
        device.agent_version = payload.agent_version
        device.last_seen = _utc_now()
        if device.status != "DISABLED":
            device.status = "ACTIVE"
        if payload.os_name:
            device.os_name = payload.os_name
        if payload.os_version:
            device.os_version = payload.os_version
        if payload.architecture:
            device.architecture = payload.architecture
        if payload.hostname:
            device.hostname = payload.hostname
    else:
        now = _utc_now()
        device = Device(
            device_name=payload.device_name,
            device_id=payload.device_id,
            ip_address=payload.ip_address,
            os_type=payload.os_type or platform,
            platform=platform,
            agent_version=payload.agent_version,
            os_name=payload.os_name or platform,
            os_version=payload.os_version,
            architecture=payload.architecture,
            hostname=payload.hostname,
            status="ACTIVE",
            last_seen=now,
            enrolled_at=now,
            registered_at=now,
        )
        db.add(device)

    db.commit()
    db.refresh(device)
    _sync_to_firebase(device)
    return device
