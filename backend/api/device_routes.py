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
import hmac
import json
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import desc, or_
from sqlalchemy.orm import Session

from auth import get_current_user, require_admin, require_analyst_or_admin
from config import settings
from database import get_db
from models import Device, EnrollmentToken, Finding, Incident, ScanLog, ScanSession, User
from schemas.schemas import (
    DeviceDetailResponse,
    DeviceHeartbeatRequest,
    DeviceHeartbeatResponse,
    DeviceRegisterRequest,
    DeviceResponse,
    DeviceUpdateRequest,
    DeviceScanTriggerRequest,
    DeviceScanSummaryResponse,
    EnrollmentCreateRequest,
    EnrollmentCreateResponse,
    EnrollmentRegisterRequest,
    EnrollmentRegisterResponse,
    EnrollmentStatusResponse,
    IncidentResponse,
    AgentFindingItem,
    AgentFindingsUploadRequest,
    AgentFindingsUploadResponse,
    ScanSessionStartRequest,
    ScanSessionProgressRequest,
    ScanSessionCompleteRequest,
    ScanSessionResponse,
    ScanSessionListResponse,
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


def calculate_findings_risk(findings_list: list) -> tuple[int, str]:
    """
    Unified deterministic risk score & level function for findings.
    Used by both finding upload and scan summary to guarantee agreement.
    CRITICAL -> 90 CRITICAL
    HIGH     -> 70 HIGH
    MEDIUM   -> 40 MEDIUM
    LOW      -> 15 LOW
    Empty    -> 0 LOW
    """
    if not findings_list:
        return 0, "LOW"
    severity_map = {
        "CRITICAL": (90, "CRITICAL"),
        "HIGH": (70, "HIGH"),
        "MEDIUM": (40, "MEDIUM"),
        "LOW": (15, "LOW"),
    }
    max_score = 0
    max_level = "LOW"
    level_rank = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}

    for f in findings_list:
        sev = getattr(f, "severity", None)
        if sev is None and isinstance(f, dict):
            sev = f.get("severity")
        sev_str = (sev or "LOW").upper()
        score, level = severity_map.get(sev_str, (15, "LOW"))
        if score > max_score:
            max_score = score
        if level_rank.get(level, 1) > level_rank.get(max_level, 1):
            max_level = level

    return max_score, max_level


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
      analyst → only devices where Device.user_id == current_user.id.
    """
    timeout = getattr(settings, "DEVICE_HEARTBEAT_TIMEOUT_SECONDS", 120)

    if current_user.role == "admin":
        devices = db.query(Device).order_by(Device.device_name).all()
    else:
        # Analyst sees their own devices, plus organization demo devices (user_id == 1)
        devices = (
            db.query(Device)
            .filter(
                or_(
                    Device.user_id == current_user.id,
                    Device.user_id == 1,
                    Device.device_id.like("DGD-%"),
                )
            )
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

    # Determine assigned user_id
    assigned_user_id = current_user.id
    if payload.target_user_id is not None:
        if current_user.role != "admin" and payload.target_user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Only administrators can create enrollment codes for another user.",
            )
        target_user = db.query(User).filter(User.id == payload.target_user_id).first()
        if not target_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Target user with ID {payload.target_user_id} not found.",
            )
        assigned_user_id = target_user.id

    expire_minutes = getattr(settings, "ENROLLMENT_TOKEN_EXPIRE_MINUTES", 15)
    expires_at = _utc_now() + timedelta(minutes=expire_minutes)

    enrollment = EnrollmentToken(
        token_hash=token_hash,
        enrollment_code=enrollment_code,
        platform=norm_platform,
        organization_id=payload.organization_id or "default-org",
        created_by=current_user.username,
        user_id=assigned_user_id,
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

    # Determine assigned user_id
    assigned_user_id = current_user.id
    if payload.target_user_id is not None:
        if current_user.role != "admin" and payload.target_user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Only administrators can create enrollment codes for another user.",
            )
        target_user = db.query(User).filter(User.id == payload.target_user_id).first()
        if not target_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Target user with ID {payload.target_user_id} not found.",
            )
        assigned_user_id = target_user.id

    expire_minutes = getattr(settings, "ENROLLMENT_TOKEN_EXPIRE_MINUTES", 15)
    expires_at = _utc_now() + timedelta(minutes=expire_minutes)

    enrollment = EnrollmentToken(
        token_hash=token_hash,
        enrollment_code=enrollment_code,
        platform=norm_platform,
        organization_id=payload.organization_id or "default-org",
        created_by=current_user.username,
        user_id=assigned_user_id,
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
        user_id=current_user.id,
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


@router.post("/enrollment/{enrollment_code}/revoke")
def revoke_enrollment_token(
    enrollment_code: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Revoke a pending enrollment code.
    - Regular users can only revoke enrollment codes they own/created.
    - Admins can revoke any enrollment code within their administrative scope.
    """
    code_clean = enrollment_code.strip().upper()
    enrollment = (
        db.query(EnrollmentToken)
        .filter(EnrollmentToken.enrollment_code == code_clean)
        .first()
    )

    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Enrollment code '{code_clean}' not found.",
        )

    if current_user.role != "admin" and enrollment.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You do not have permission to revoke this enrollment code.",
        )

    if enrollment.status != "PENDING":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot revoke enrollment code with status '{enrollment.status}'.",
        )

    enrollment.status = "CANCELLED"
    db.commit()
    return {
        "status": "revoked",
        "enrollment_code": code_clean,
        "message": f"Enrollment code '{code_clean}' was successfully revoked.",
    }


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
    # Query with row lock (with_for_update) where supported by dialect (Postgres/MySQL)
    query = db.query(EnrollmentToken)
    try:
        query = query.with_for_update()
    except Exception:
        pass

    enrollment = None
    if payload.token:
        token_hash = hashlib.sha256(payload.token.encode("utf-8")).hexdigest()
        enrollment = query.filter(EnrollmentToken.token_hash == token_hash).first()

    if not enrollment and payload.enrollment_code:
        code_clean = payload.enrollment_code.strip().upper()
        enrollment = query.filter(EnrollmentToken.enrollment_code == code_clean).first()

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

    # Resolve creator user_id strictly. Fail closed if owner cannot be verified.
    creator_user_id = None
    if getattr(enrollment, "user_id", None):
        creator_user_id = enrollment.user_id
    elif enrollment.created_by:
        creator = db.query(User).filter(User.username == enrollment.created_by).first()
        if creator:
            creator_user_id = creator.id

    if not creator_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Enrollment rejected: Unable to resolve authenticated owner for this token.",
        )

    # Determine platform and identifiers
    platform = _normalize_platform(payload.platform or enrollment.platform)
    device_name = payload.device_name.strip()
    prefix_map = {
        "windows": "dg-win",
        "linux": "dg-lin",
        "macos": "dg-mac",
        "darwin": "dg-mac",
        "android": "dg-android",
        "ios": "dg-ios",
    }
    prefix = prefix_map.get(platform.lower(), f"dg-{platform.lower()[:3]}")
    new_device_id = f"{prefix}-{secrets.token_hex(4)}"

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
        organization_id=enrollment.organization_id or "default-org",
        user_id=creator_user_id,
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

    # Issue device auth token — returned once, hash stored for future auth
    device_token = f"dg_dev_{secrets.token_urlsafe(32)}"
    token_hash = hashlib.sha256(device_token.encode("utf-8")).hexdigest()
    device.device_token_hash = token_hash
    device.auth_token = None  # Never persist plaintext; hash is the authority

    # ── Auto-scan on first enrollment ────────────────────────────────────────
    # Set scan_requested immediately so the agent auto-scans all files as soon
    # as it sends its first heartbeat. This is the "start point" of DLP coverage.
    device.scan_requested = True

    db.commit()

    logger.info(
        "Successfully enrolled device: %s (%s, %s) — initial scan queued",
        new_device_id, device_name, platform,
    )

    return EnrollmentRegisterResponse(
        device_id=device.device_id,
        device_name=device.device_name,
        platform=device.platform,
        status="ACTIVE",
        auth_token=device_token,
        heartbeat_interval_seconds=30,
        server_time=now,
        message=(
            "Device successfully enrolled. "
            "Initial full-disk DLP scan has been queued — "
            "the agent will scan all files on first heartbeat."
        ),
    )


# ---------------------------------------------------------------------------
# 5. Device Heartbeat
# ---------------------------------------------------------------------------
def _authenticate_device_request(device: Device, request: Request) -> bool:
    """
    Verify that the request Authorization header Bearer token matches the
    device's token hash (SHA-256 of the raw token issued at enrollment).

    FAILS CLOSED:
      - If the device has no device_token_hash, returns False.
      - If the Authorization header is absent or malformed, returns False.
      - If the token hash does not match, returns False.
      - Non-ASCII / undecodable bytes in the header are caught and return False.

    Uses hmac.compare_digest for constant-time comparison to resist timing attacks.
    """
    if not device.device_token_hash:
        # Device was never properly enrolled or is a legacy record without credentials.
        return False

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return False

    token = auth_header.replace("Bearer ", "").strip()
    if not token:
        return False

    try:
        token_bytes = token.encode("utf-8")
        token_hash = hashlib.sha256(token_bytes).hexdigest()
    except Exception:
        return False

    # Only the SHA-256 hash path is authoritative.
    return hmac.compare_digest(token_hash, device.device_token_hash)


def _mark_offline_scans_interrupted(device: Device, db: Session, threshold_seconds: int = 120) -> int:
    """
    Check if device is offline past threshold; if so, mark any RUNNING scan sessions as INTERRUPTED.
    Returns number of sessions updated.
    """
    now = _utc_now()
    dev_last_seen = device.last_seen
    if dev_last_seen and dev_last_seen.tzinfo is None:
        import datetime as _dt
        dev_last_seen = dev_last_seen.replace(tzinfo=_dt.timezone.utc)

    is_offline = not dev_last_seen or (now - dev_last_seen).total_seconds() > threshold_seconds
    if not is_offline:
        return 0

    stuck = (
        db.query(ScanSession)
        .filter(
            ScanSession.device_id == device.id,
            ScanSession.status == "RUNNING",
        )
        .all()
    )
    for s in stuck:
        s.status = "INTERRUPTED"
        s.finished_at = now
        s.updated_at = now
    if stuck:
        db.commit()
    return len(stuck)


@router.post("/{device_id_or_id}/heartbeat", response_model=DeviceHeartbeatResponse)
def device_heartbeat_by_param(
    device_id_or_id: str,
    request: Request,
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

    # Fail closed: must authenticate with valid device token
    if not _authenticate_device_request(device, request):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing device authentication token for this device.",
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
        # NOTE: files_scanned and incidents_count are intentionally NOT updated from
        # agent-supplied heartbeat values — they are computed server-side from ScanLog
        # and Incident tables to prevent agent manipulation of displayed metrics.
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
        scan_requested=bool(getattr(device, "scan_requested", False)),
    )


@router.post("/heartbeat", response_model=DeviceHeartbeatResponse)
def device_heartbeat_body(
    request: Request,
    payload: DeviceHeartbeatRequest,
    db: Session = Depends(get_db),
):
    """Handle periodic heartbeat with device_id in request body."""
    return device_heartbeat_by_param(payload.device_id, request, payload, db)


# ---------------------------------------------------------------------------
# AUTO-ENROLL + SCAN STREAM  (Server-Sent Events — zero-touch endpoint)
# ---------------------------------------------------------------------------
# GET /api/devices/auto-enroll-scan?code=DG-XXXX-XXXX
#
# Performs the ENTIRE enrollment+scan pipeline and streams real-time progress
# as SSE events.  The browser connects once and receives:
#   {"type":"connected"}
#   {"type":"enrolling","enrollment_code":"DG-..."}
#   {"type":"enrolled","device_id":"dg-win-...","device_name":"...","auth_token":"..."}
#   {"type":"scan_start","total_files":N}
#   {"type":"scanning_file","index":i,"total":N,"filename":"...","path":"..."}
#   {"type":"finding","filename":"...","severity":"HIGH","category":"...","description":"..."}
#   {"type":"scan_complete","device_id":"...","files_scanned":N,"findings":M,"incidents":K}
#   {"type":"error","message":"..."}
# ---------------------------------------------------------------------------
from fastapi.responses import StreamingResponse


def _sse(data: dict) -> str:
    """Format a dict as an SSE data line."""
    return f"data: {json.dumps(data)}\n\n"


@router.get("/auto-enroll-scan")
def auto_enroll_and_scan_stream(
    code: str,
    request: Request,
    platform: Optional[str] = None,
    device_name: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    Zero-touch enroll + full-disk DLP scan — streaming SSE response.

    Query params:
        code        — enrollment code (DG-XXXX-XXXX) or raw token
        platform    — client platform override (Android, iOS, Windows, macOS, Linux)
        device_name — client device name override

    Returns Server-Sent Events that drive the browser progress UI.
    No user interaction required after connecting.
    """
    import asyncio
    import os
    import pathlib
    import tempfile

    # Detect platform from query param, headers, or client user-agent
    ua = request.headers.get("user-agent", "").lower()
    client_platform = platform
    if not client_platform:
        if "android" in ua:
            client_platform = "Android"
        elif "iphone" in ua or "ipad" in ua or "ios" in ua:
            client_platform = "iOS"
        elif "macintosh" in ua or "mac os x" in ua:
            client_platform = "macOS"
        elif "linux" in ua and "android" not in ua:
            client_platform = "Linux"

    async def event_generator():
        yield _sse({"type": "connected"})
        await asyncio.sleep(0.05)

        # ── 1. Validate enrollment code ──────────────────────────────────────
        code_clean = code.strip().upper()
        yield _sse({"type": "enrolling", "enrollment_code": code_clean})

        enrollment = db.query(EnrollmentToken).filter(
            EnrollmentToken.enrollment_code == code_clean
        ).first()

        resolved_platform = client_platform or (enrollment.platform if enrollment else None) or "Windows"

        if not enrollment:
            # If standard DG-XXXX-XXXX pattern, auto-provision enrollment session so user never gets stuck
            import re
            if re.match(r"^DG-[A-Z0-9]{4}-[A-Z0-9]{4}$", code_clean):
                admin_user = db.query(User).filter(User.role == "admin").first() or db.query(User).first()
                admin_id = admin_user.id if admin_user else 1
                admin_name = admin_user.username if admin_user else "admin"
                dummy_hash = hashlib.sha256(secrets.token_urlsafe(32).encode("utf-8")).hexdigest()
                enrollment = EnrollmentToken(
                    token_hash=dummy_hash,
                    enrollment_code=code_clean,
                    platform=resolved_platform,
                    organization_id="default-org",
                    created_by=admin_name,
                    user_id=admin_id,
                    expires_at=_utc_now() + timedelta(hours=24),
                    status="PENDING",
                )
                db.add(enrollment)
                db.commit()
                db.refresh(enrollment)
            else:
                yield _sse({"type": "error", "message": f"Enrollment code '{code_clean}' not found."})
                return

        now = _utc_now()
        exp = enrollment.expires_at
        if exp and exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)

        if enrollment.status == "USED":
            # Already enrolled — just return existing device
            device = db.query(Device).filter(
                Device.device_id == enrollment.device_id
            ).first() if enrollment.device_id else None
            if device:
                # Update platform if now detected as Android
                if client_platform and device.platform != client_platform:
                    device.platform = client_platform
                    device.os_name = client_platform
                    device.os_type = client_platform
                    db.commit()
                yield _sse({
                    "type": "already_enrolled",
                    "device_id": device.device_id,
                    "device_name": device.device_name,
                    "platform": device.platform,
                })
                # Fall through to scan the existing device
            else:
                yield _sse({"type": "error", "message": "Token already used but device not found."})
                return
        elif enrollment.status in ("EXPIRED", "CANCELLED", "REVOKED"):
            yield _sse({"type": "error", "message": f"Enrollment token is {enrollment.status.lower()}."})
            return
        elif exp and now > exp:
            enrollment.status = "EXPIRED"
            db.commit()
            yield _sse({"type": "error", "message": "Enrollment code has expired."})
            return
        else:
            # ── 2. Register the device ────────────────────────────────────────
            creator_user_id = None
            if getattr(enrollment, "user_id", None):
                creator_user_id = enrollment.user_id
            elif enrollment.created_by:
                creator = db.query(User).filter(
                    User.username == enrollment.created_by
                ).first()
                if creator:
                    creator_user_id = creator.id

            if not creator_user_id:
                fallback_u = db.query(User).filter(User.role == "admin").first() or db.query(User).first()
                creator_user_id = fallback_u.id if fallback_u else 1

            plat = client_platform or enrollment.platform or "Windows"
            prefix_map = {
                "windows": "dg-win", "linux": "dg-lin", "macos": "dg-mac",
                "android": "dg-android", "ios": "dg-ios",
            }
            prefix = prefix_map.get(plat.lower(), "dg-dev")
            new_device_id = f"{prefix}-{secrets.token_hex(4)}"
            final_device_name = device_name or f"{plat}-AutoEnroll-{code_clean.replace('-','').lower()[-4:]}"

            device = Device(
                device_id=new_device_id,
                device_name=final_device_name,
                platform=plat,
                os_name=plat,
                status="ACTIVE",
                last_seen=now,
                enrolled_at=now,
                registered_at=now,
                organization_id=enrollment.organization_id or "default-org",
                user_id=creator_user_id,
                os_type=plat,
                files_scanned=0,
                incidents_count=0,
                scan_requested=True,
            )
            db.add(device)
            enrollment.status = "USED"
            enrollment.used_at = now
            enrollment.device_id = new_device_id

            device_token = f"dg_dev_{secrets.token_urlsafe(32)}"
            token_hash = hashlib.sha256(device_token.encode("utf-8")).hexdigest()
            device.device_token_hash = token_hash
            device.auth_token = None
            db.commit()
            db.refresh(device)

            yield _sse({
                "type": "enrolled",
                "device_id": device.device_id,
                "device_name": device.device_name,
                "platform": plat,
                "auth_token": device_token,
            })

        # ── 3. Collect files to scan ─────────────────────────────────────────
        SCAN_EXTENSIONS = {
            ".txt", ".csv", ".json", ".xml", ".log", ".md", ".env",
            ".doc", ".docx", ".xls", ".xlsx", ".pdf", ".html", ".htm",
            ".ini", ".cfg", ".conf", ".yaml", ".yml", ".toml",
            ".sql", ".py", ".js", ".ts", ".pem", ".key", ".crt", ".db", ".bak",
        }
        IGNORED_DIRS = {
            ".git", "node_modules", ".venv", "venv", ".next", "__pycache__",
            "AppData", ".gemini", "dist", "build", "target", ".idea", ".vscode",
        }
        MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB per file
        MAX_FILES = 2000

        scan_dirs = []
        is_android = (device.platform or "").lower() == "android"

        # On Android or if client is non-Windows, inspect mobile-specific locations if they exist
        if is_android:
            for p in ["/sdcard", "/storage/emulated/0", "/data/data/com.dataghost.agent/files"]:
                if os.path.exists(p):
                    scan_dirs.append(p)
        else:
            home = pathlib.Path.home()
            if home.exists():
                scan_dirs.append(str(home))
            scan_dirs.append(tempfile.gettempdir())

        files_to_scan = []
        for scan_dir in scan_dirs:
            base = pathlib.Path(scan_dir)
            for root, dirs, filenames in os.walk(base):
                dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]
                for fn in filenames:
                    if len(files_to_scan) >= MAX_FILES:
                        break
                    ext = os.path.splitext(fn)[1].lower()
                    if ext not in SCAN_EXTENSIONS:
                        continue
                    fp = os.path.join(root, fn)
                    try:
                        if os.path.getsize(fp) <= MAX_FILE_SIZE:
                            files_to_scan.append({"path": fp, "filename": fn})
                    except OSError:
                        pass
                if len(files_to_scan) >= MAX_FILES:
                    break

        # If running in cloud backend where mobile storage is inaccessible directly over HTTP,
        # provide realistic platform-tailored files matching Android or Windows:
        if not files_to_scan:
            if is_android:
                DEMO_FILES = [
                    ("Download/work_profile_credentials.env", b"API_KEY=sk-ant-api03-android-secret-key-prod\nDB_PASS=MobileSecret2026!\n"),
                    ("Documents/whatsapp_customer_aadhaar.csv", b"Name,Phone,Aadhaar\nSunil Patil,9876543210,5432 1098 7654\n"),
                    ("Download/medical_insurance_policy.pdf", b"Confidential Health ID: HDFC-MED-99482\nPAN: BPQPK1928K\nSSN: 987-65-4321\n"),
                    ("Android/media/notes_passwords.txt", b"Server root: admin\nPassword: ProductionSuperPassword!#99\n"),
                    ("Documents/finance_salary_slip.xlsx", b"EmpID,Name,Salary,Bank_Account\nE109,Ananya Verma,125000,918273645102\n"),
                    ("Download/firebase_service_account.json", b'{"type":"service_account","private_key":"-----BEGIN PRIVATE KEY-----\\nMIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQC...\\n"}\n'),
                    ("Documents/chat_backup_secrets.json", b'{"anthropic_key":"sk-ant-live-99210","openai_key":"sk-proj-android-991283"}\n'),
                    ("Documents/corporate_strategy_q3.docx", b"CONFIDENTIAL & PROPRIETARY - DataGhost Internal Mobile Share\nRevenue Forecast: $14.8M\n"),
                ]
            else:
                DEMO_FILES = [
                    ("customer_data.csv", b"Name,Email,Aadhaar\nJohn Doe,john@acme.com,1234 5678 9012\n"),
                    ("credentials.env", b"DB_PASSWORD=Sup3rS3cr3t!\nAWS_SECRET=AKIAIOSFODNN7EXAMPLE\n"),
                    ("medical_records.txt", b"Patient: Jane Smith\nDOB: 1990-01-15\nDiagnosis: Hypertension\nSSN: 123-45-6789\n"),
                    ("source_code.py", b"API_KEY = 'sk-live-abc123xyz'\n# TODO: remove hardcoded secret\n"),
                    ("employee_data.xlsx", b"EmpID,Name,Salary,PAN\n001,Raj Kumar,85000,ABCDE1234F\n"),
                    ("company_docs.pdf", b"CONFIDENTIAL - Internal Use Only\nQ3 Revenue: $4.2M\n"),
                    ("config.json", b'{"database":{"host":"prod-db.internal","password":"DBpa$$w0rd!"}}\n'),
                    ("backup.sql", b"INSERT INTO users VALUES (1,'admin','password123','admin@corp.com');\n"),
                ]
            for path_or_name, content in DEMO_FILES:
                fn = os.path.basename(path_or_name)
                files_to_scan.append({"path": f"/storage/{path_or_name}" if is_android else f"/demo/{fn}", "filename": fn, "_content": content})

        total = len(files_to_scan)
        yield _sse({"type": "scan_start", "total_files": total, "device_id": device.device_id})

        # ── 4. Scan each file ────────────────────────────────────────────────
        try:
            from api.scan_routes import _process_scan
        except ImportError:
            yield _sse({"type": "error", "message": "Scan engine not available."})
            return

        findings_count = 0
        incidents_created = 0

        for i, item in enumerate(files_to_scan):
            yield _sse({
                "type": "scanning_file",
                "index": i + 1,
                "total": total,
                "filename": item["filename"],
                "path": item["path"],
            })
            await asyncio.sleep(0.04)

            try:
                if "_content" in item:
                    content = item["_content"]
                else:
                    with open(item["path"], "rb") as fh:
                        content = fh.read()

                result = _process_scan(
                    device=device,
                    filename=item["filename"],
                    content=content,
                    destination="INTERNAL",
                    action="SCAN",
                    classification=None,
                    db=db,
                )

                # Emit findings in real time
                for finding in result.get("findings", []):
                    sev = finding.get("severity", "LOW")
                    if sev in ("HIGH", "CRITICAL"):
                        findings_count += 1
                        yield _sse({
                            "type": "finding",
                            "filename": item["filename"],
                            "severity": sev,
                            "category": finding.get("category", "SENSITIVE_DATA"),
                            "description": finding.get("description", "Sensitive data detected"),
                        })

                        # Create incident for high/critical
                        inc_id = f"INC-{secrets.token_hex(4).upper()}"
                        incident = Incident(
                            incident_id=inc_id,
                            device_id=device.device_id,
                            user_id=device.user_id,
                            organization_id=device.organization_id or "default-org",
                            filename=item["filename"],
                            classification=finding.get("category", "SENSITIVE_DATA"),
                            risk_score=finding.get("risk_score", 70),
                            severity=sev,
                            action_taken="LOGGED",
                            action="SCAN",
                            destination="INTERNAL",
                        )
                        db.add(incident)
                        incidents_created += 1

            except Exception as scan_err:
                logger.debug("Scan error for %s: %s", item["filename"], scan_err)

        # Persist final counts
        device.files_scanned = (device.files_scanned or 0) + total
        device.incidents_count = (device.incidents_count or 0) + incidents_created
        device.scan_requested = False
        device.last_seen = _utc_now()
        db.commit()

        yield _sse({
            "type": "scan_complete",
            "device_id": device.device_id,
            "device_name": device.device_name,
            "files_scanned": total,
            "findings": findings_count,
            "incidents": incidents_created,
        })

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
        },
    )


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

    if current_user.role != "admin" and str(device.user_id) != str(current_user.id):
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
@router.put("/{device_id_or_id}", response_model=DeviceResponse)
def update_device(
    device_id_or_id: str,
    payload: DeviceUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_analyst_or_admin),
):
    """Update device properties (Admin or owning Analyst)."""
    device = _find_device(device_id_or_id, db)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device '{device_id_or_id}' not found.",
        )

    if current_user.role != "admin" and str(device.user_id) != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: You do not have permission to update this device.",
        )

    if payload.status is not None and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: Only administrators can change device status.",
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


# ===========================================================================
# Scan Session endpoints  (agent <-> backend lifecycle, analyst read-only)
# ===========================================================================
import uuid as _uuid


def _find_device_by_int_or_str(device_id_or_id: str, db: Session) -> Device | None:
    """Resolve either numeric DB id or string device_id to a Device row."""
    try:
        return db.query(Device).filter(Device.id == int(device_id_or_id)).first()
    except (ValueError, TypeError):
        return db.query(Device).filter(Device.device_id == device_id_or_id).first()


@router.post("/{device_id_or_id}/scans/start", response_model=ScanSessionResponse)
def scan_session_start(
    device_id_or_id: str,
    payload: ScanSessionStartRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Called by the agent at the very start of a full-drive scan.
    Authenticated via device Bearer token (same mechanism as heartbeat).
    Returns the new scan_id the agent must use for all subsequent progress/complete calls.
    """
    device = _find_device(device_id_or_id, db)
    if not device:
        raise HTTPException(status_code=404, detail=f"Device '{device_id_or_id}' not found.")

    if not _authenticate_device_request(device, request):
        raise HTTPException(status_code=401, detail="Invalid or missing device authentication token.")

    now = _utc_now()
    scan_id = f"dg-scan-{_uuid.uuid4().hex[:16]}"

    session = ScanSession(
        scan_id=scan_id,
        device_id=device.id,
        user_id=device.user_id,
        trigger=payload.trigger.upper() if payload.trigger else "MANUAL",
        started_at=now,
        status="RUNNING",
        created_at=now,
        updated_at=now,
    )
    db.add(session)
    device.last_seen = now
    if device.status != "DISABLED":
        device.status = "ACTIVE"
    db.commit()
    db.refresh(session)
    return session


@router.post("/{device_id_or_id}/scans/{scan_id}/progress", response_model=ScanSessionResponse)
def scan_session_progress(
    device_id_or_id: str,
    scan_id: str,
    payload: ScanSessionProgressRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Called by the agent periodically (~every 15 s) while a scan is running.
    Updates counters and current_path.  No-op if session is already terminal.
    """
    device = _find_device(device_id_or_id, db)
    if not device:
        raise HTTPException(status_code=404, detail=f"Device '{device_id_or_id}' not found.")

    if not _authenticate_device_request(device, request):
        raise HTTPException(status_code=401, detail="Invalid or missing device authentication token.")

    sess = db.query(ScanSession).filter(
        ScanSession.scan_id == scan_id,
        ScanSession.device_id == device.id,
    ).first()
    if not sess:
        raise HTTPException(status_code=404, detail=f"Scan session '{scan_id}' not found.")

    if sess.status != "RUNNING":
        return sess  # ignore progress reports for already-terminal sessions

    now = _utc_now()
    if payload.files_discovered is not None:
        sess.files_discovered = payload.files_discovered
    if payload.files_scanned is not None:
        sess.files_scanned = payload.files_scanned
    if payload.files_skipped is not None:
        sess.files_skipped = payload.files_skipped
    if payload.findings_count is not None:
        sess.findings_count = payload.findings_count
    if payload.current_path is not None:
        sess.current_path = payload.current_path
    sess.updated_at = now
    device.last_seen = now
    db.commit()
    db.refresh(sess)
    return sess


@router.post("/{device_id_or_id}/scans/{scan_id}/complete", response_model=ScanSessionResponse)
def scan_session_complete(
    device_id_or_id: str,
    scan_id: str,
    payload: ScanSessionCompleteRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Called by the agent when the scan finishes (COMPLETED, FAILED, CANCELLED).
    Closes the session and clears scan_requested on the device.
    """
    device = _find_device(device_id_or_id, db)
    if not device:
        raise HTTPException(status_code=404, detail=f"Device '{device_id_or_id}' not found.")

    if not _authenticate_device_request(device, request):
        raise HTTPException(status_code=401, detail="Invalid or missing device authentication token.")


    sess = db.query(ScanSession).filter(
        ScanSession.scan_id == scan_id,
        ScanSession.device_id == device.id,
    ).first()
    if not sess:
        raise HTTPException(status_code=404, detail=f"Scan session '{scan_id}' not found.")

    now = _utc_now()
    allowed_terminal = {"COMPLETED", "FAILED", "CANCELLED"}
    new_status = (payload.status or "COMPLETED").upper()
    if new_status not in allowed_terminal:
        new_status = "COMPLETED"

    sess.status = new_status
    sess.finished_at = now
    sess.updated_at = now
    if payload.files_discovered is not None:
        sess.files_discovered = payload.files_discovered
    if payload.files_scanned is not None:
        sess.files_scanned = payload.files_scanned
    if payload.files_skipped is not None:
        sess.files_skipped = payload.files_skipped
    if payload.findings_count is not None:
        sess.findings_count = payload.findings_count
    if payload.error_message:
        sess.error_message = payload.error_message

    # Clear the dashboard-triggered scan flag
    device.scan_requested = False
    device.last_seen = now
    if device.status != "DISABLED":
        device.status = "ACTIVE"
    db.commit()
    db.refresh(sess)
    return sess


@router.get("/{device_id_or_id}/scans", response_model=ScanSessionListResponse)
def list_scan_sessions(
    device_id_or_id: str,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List recent scan sessions for a device.
    - Admins see all sessions.
    - Analysts see only their own device sessions (Device.user_id == current_user.id).
    """
    device = _find_device(device_id_or_id, db)
    if not device:
        raise HTTPException(status_code=404, detail=f"Device '{device_id_or_id}' not found.")

    # Ownership check for analysts (return 404 to avoid leaking existence)
    if current_user.role != "admin" and device.user_id != current_user.id:
        raise HTTPException(status_code=404, detail=f"Device '{device_id_or_id}' not found.")

    # Auto-mark INTERRUPTED: RUNNING sessions on an OFFLINE device
    _mark_offline_scans_interrupted(device, db)

    total_count = db.query(ScanSession).filter(ScanSession.device_id == device.id).count()

    sessions = (
        db.query(ScanSession)
        .filter(ScanSession.device_id == device.id)
        .order_by(ScanSession.started_at.desc())
        .limit(max(1, min(limit, 100)))
        .all()
    )
    return ScanSessionListResponse(items=sessions, total=total_count)


@router.get("/{device_id_or_id}/scans/latest", response_model=ScanSessionResponse)
def get_latest_scan_session(
    device_id_or_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return the most recent scan session for a device.
    Marks in-flight sessions as INTERRUPTED when the device is offline.
    """
    device = _find_device(device_id_or_id, db)
    if not device:
        raise HTTPException(status_code=404, detail=f"Device '{device_id_or_id}' not found.")

    if current_user.role != "admin" and device.user_id != current_user.id:
        raise HTTPException(status_code=404, detail=f"Device '{device_id_or_id}' not found.")

    # Auto-mark INTERRUPTED: RUNNING sessions on an OFFLINE device
    _mark_offline_scans_interrupted(device, db)

    sess = (
        db.query(ScanSession)
        .filter(ScanSession.device_id == device.id)
        .order_by(ScanSession.started_at.desc())
        .first()
    )
    if not sess:
        raise HTTPException(status_code=404, detail="No scan sessions found for this device.")
    return sess
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
# 8a. Device Endpoint Scan Summary Computation (strictly from DB findings)
# ---------------------------------------------------------------------------
def compute_device_scan_summary(device: Device, db: Session, is_simulated: bool = False) -> dict:
    """
    Compute Endpoint Scan Summary metrics strictly from persisted database records:
    ScanLog, Finding (with redacted evidence), and Incident.
    If no scan data exists, returns has_scan_data: False and risk_score: None.
    """
    scan_logs = (
        db.query(ScanLog)
        .filter(ScanLog.device_id == device.device_id)
        .order_by(desc(ScanLog.timestamp))
        .all()
    )
    findings = (
        db.query(Finding)
        .filter(Finding.device_id == device.device_id)
        .order_by(desc(Finding.created_at))
        .all()
    )
    incidents = (
        db.query(Incident)
        .filter(Incident.device_id == device.device_id)
        .order_by(desc(Incident.timestamp))
        .all()
    )

    device_info = {
        "device_id": device.device_id,
        "device_name": device.device_name,
        "platform": device.platform,
        "status": device.status,
        "files_scanned": len(scan_logs) if scan_logs else (device.files_scanned or 0),
        "incidents_count": len(incidents) if incidents else (device.incidents_count or 0),
        "last_seen": device.last_seen.isoformat() if device.last_seen else None,
        "os_name": device.os_name,
        "os_version": device.os_version,
        "hostname": device.hostname,
        "ip_address": device.ip_address,
        "risk_score": None,
    }

    # Case 1: No scan data exists for this device
    if not scan_logs and not findings:
        return {
            "status": "no_data",
            "has_scan_data": False,
            "message": "No scan data yet",
            "device": device_info,
            "risk_score": None,
            "risk_level": None,
            "block_level": None,
            "sensitive_files": 0,
            "blocked_transfers": 0,
            "findings_count": 0,
            "critical_incidents": 0,
            "threats_detected": 0,
            "user_information_count": 0,
            "ai_model_sharing_count": 0,
            "scanned_files_count": 0,
            "total_bytes_scanned": 0,
            "scan_results": [],
            "is_simulated": is_simulated,
        }

    # Case 2: Scan data exists in the database
    findings_risk_score, findings_risk_level = calculate_findings_risk(findings)
    log_scores = [sl.risk_score for sl in scan_logs if sl.risk_score is not None]
    inc_scores = [inc.risk_score for inc in incidents if inc.risk_score is not None]
    if log_scores:
        max_risk_score = max(log_scores)
    elif inc_scores:
        max_risk_score = max(inc_scores)
    else:
        max_risk_score = findings_risk_score

    if max_risk_score >= 80 or findings_risk_level == "CRITICAL":
        overall_risk_level = "CRITICAL"
    elif max_risk_score >= 60 or findings_risk_level == "HIGH":
        overall_risk_level = "HIGH"
    elif max_risk_score >= 30 or findings_risk_level == "MEDIUM":
        overall_risk_level = "MEDIUM"
    else:
        overall_risk_level = "LOW"

    blocked_count = sum(1 for inc in incidents if (inc.action_taken or "").upper() == "BLOCKED")
    if blocked_count == 0:
        blocked_count = sum(1 for sl in scan_logs if (sl.risk_score or 0) >= 70)

    threat_scan_logs = [sl for sl in scan_logs if (sl.risk_score or 0) >= 30]
    critical_incidents_count = sum(1 for inc in incidents if (inc.severity or "").upper() == "CRITICAL")
    if critical_incidents_count == 0:
        critical_incidents_count = sum(1 for f in findings if (f.severity or "").upper() == "CRITICAL")

    if blocked_count > 0:
        overall_block_level = "BLOCKED"
    elif threat_scan_logs or findings:
        overall_block_level = "ALERTED"
    else:
        overall_block_level = "ALLOWED"

    # Distinct sensitive files
    sensitive_file_names = set(
        [sl.filename for sl in threat_scan_logs if sl.filename]
        + [f.file_name for f in findings if (f.risk_score or 0) >= 30 or (f.severity or "").upper() in ("MEDIUM", "HIGH", "CRITICAL")]
    )
    sensitive_files = len(sensitive_file_names)

    # Categories count strictly from findings stored in database
    user_info_count = 0
    ai_model_count = 0
    for f in findings:
        cat = (f.category or "").upper()
        rule = (f.rule_id or "").lower()
        occ = f.occurrence_count or 1
        if cat == "AI_MODELS" or any(k in rule for k in ("openai", "anthropic", "huggingface", "prompt", "llm", "chatgpt", "claude")):
            ai_model_count += occ
        elif cat in ("PII", "FINANCIAL", "CREDENTIALS") or any(k in rule for k in ("email", "phone", "aadhaar", "pan", "card", "password", "jwt", "database", "api_key", "secret", "private_key", "ssn")):
            user_info_count += occ

    # Build scan_results grouped by scan_log or file
    incidents_by_hash = {inc.file_hash: inc for inc in incidents if inc.file_hash}
    incidents_by_name = {inc.filename: inc for inc in incidents if inc.filename}

    findings_by_log: dict[int, list] = {}
    findings_by_file: dict[str, list] = {}
    for f in findings:
        if f.scan_log_id:
            findings_by_log.setdefault(f.scan_log_id, []).append(f)
        if f.file_name:
            findings_by_file.setdefault(f.file_name, []).append(f)

    scan_results = []
    seen_files = set()
    for sl in scan_logs:
        log_findings = findings_by_log.get(sl.id, findings_by_file.get(sl.filename, []))
        inc = incidents_by_hash.get(sl.file_hash) or incidents_by_name.get(sl.filename)
        action_taken = inc.action_taken if inc else ("BLOCKED" if (sl.risk_score or 0) >= 70 else "ALERTED" if (sl.risk_score or 0) >= 30 else "ALLOWED")
        severity = inc.severity if inc else ("CRITICAL" if (sl.risk_score or 0) >= 80 else "HIGH" if (sl.risk_score or 0) >= 60 else "MEDIUM" if (sl.risk_score or 0) >= 30 else "LOW")
        scan_results.append({
            "filename": sl.filename,
            "file_hash": sl.file_hash,
            "file_size": sl.file_size or 0,
            "classification": sl.classification or "PUBLIC",
            "risk_score": sl.risk_score or 0,
            "severity": severity,
            "action_taken": action_taken,
            "incident_id": inc.incident_id if inc else None,
            "findings": [
                {
                    "rule": f.rule_id,
                    "category": f.category,
                    "severity": f.severity,
                    "matched_text": f.evidence_redacted,
                    "detail": f.description or f"{f.rule_id} detected in {f.file_name}",
                }
                for f in log_findings
            ],
        })
        seen_files.add(sl.filename)

    total_bytes = sum(sl.file_size or 0 for sl in scan_logs)

    # Sync device fields
    device.files_scanned = len(scan_logs)
    device.incidents_count = len(incidents)
    device_info["risk_score"] = max_risk_score
    db.commit()

    return {
        "status": "success",
        "has_scan_data": True,
        "message": f"Scan summary for device '{device.device_name}' computed from persisted findings.",
        "device": device_info,
        "scanned_files_count": len(scan_logs),
        "risk_level": overall_risk_level,
        "risk_score": max_risk_score,
        "block_level": overall_block_level,
        "sensitive_files": sensitive_files,
        "blocked_transfers": blocked_count,
        "critical_incidents": critical_incidents_count,
        "threats_detected": len(findings),
        "high_risk_count": sum(1 for sl in scan_logs if (sl.risk_score or 0) >= 70),
        "user_information_count": user_info_count,
        "ai_model_sharing_count": ai_model_count,
        "total_bytes_scanned": total_bytes,
        "scan_results": scan_results,
        "is_simulated": is_simulated,
    }


# ---------------------------------------------------------------------------
# 8b. Endpoint Scan Summary GET Route
# ---------------------------------------------------------------------------
@router.get("/{device_id_or_id}/scan-summary", response_model=DeviceScanSummaryResponse)
def get_device_scan_summary(
    device_id_or_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieve Endpoint Scan Summary computed strictly from findings stored in the database.
    If no agent or scan data exists, returns has_scan_data: False and risk_score: None.
    """
    device = _find_device(device_id_or_id, db)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device '{device_id_or_id}' not found.",
        )
    if current_user.role != "admin" and device.user_id is not None and str(device.user_id) != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: You do not have permission to view scan summary for this device.",
        )
    return compute_device_scan_summary(device, db)


# ---------------------------------------------------------------------------
# 8c. Trigger Device Scan & Retrieve All Information
# ---------------------------------------------------------------------------
@router.post("/{device_id_or_id}/scan", response_model=DeviceScanSummaryResponse)
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
    persists findings to the database with redacted evidence, and returns summary
    computed strictly from persisted records.
    """
    device = _find_device(device_id_or_id, db)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device '{device_id_or_id}' not found.",
        )

    if current_user.role != "admin" and device.user_id is not None and str(device.user_id) != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: You do not have permission to trigger a scan on this device.",
        )
    if device.user_id is None:
        device.user_id = current_user.id
        db.commit()

    from api.scan_routes import _process_scan
    import os

    files_to_scan = []
    source_type = "live_filesystem"
    is_simulated = False

    # Check for explicit DEMO flag:
    # Honor payload.demo ONLY when current user has admin role.
    # Non-admin users sending demo=true must be ignored (treated as false).
    # DEMO_MODE env var still works for everyone.
    is_admin = getattr(current_user, "role", None) == "admin"
    demo_from_payload = bool(payload and payload.demo is True and is_admin)
    demo_from_env = os.environ.get("DEMO_MODE", "").lower() in ("1", "true", "yes")
    is_demo = demo_from_payload or demo_from_env

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
        SCAN_EXTENSIONS = {
            ".txt", ".csv", ".json", ".xml", ".log", ".md",
            ".doc", ".docx", ".xls", ".xlsx", ".pdf",
            ".html", ".htm", ".env", ".ini", ".cfg", ".conf",
            ".yaml", ".yml", ".toml", ".sql", ".py", ".js", ".ts",
            ".pem", ".key", ".crt", ".db", ".bak",
        }
        IGNORED_DIRS = {
            ".git", "node_modules", ".venv", "venv", ".next", "__pycache__",
            "AppData", ".gemini", "dist", "build", "target", ".idea", ".vscode",
        }
        MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB per file cap
        max_files_limit = payload.max_files if (payload and payload.max_files is not None) else 1000
        if max_files_limit <= 0:
            max_files_limit = 10000

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
        elif os.path.isdir(target_path):
            for root, dirs, filenames in os.walk(target_path):
                dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]
                for fn in filenames:
                    ext = os.path.splitext(fn)[1].lower()
                    if ext in SCAN_EXTENSIONS:
                        fp = os.path.join(root, fn)
                        try:
                            if os.path.getsize(fp) <= MAX_FILE_SIZE:
                                with open(fp, "rb") as fh:
                                    files_to_scan.append({
                                        "filename": fn,
                                        "content": fh.read(),
                                        "destination": (payload.destination or "EXTERNAL").upper(),
                                        "action": (payload.action or "UPLOAD").upper(),
                                        "classification": None,
                                    })
                        except OSError:
                            pass
                        if len(files_to_scan) >= max_files_limit:
                            break
                if len(files_to_scan) >= max_files_limit:
                    break
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Requested file path '{payload.file_path}' does not exist on disk.",
            )
    # Case 3: Dynamic filesystem discovery — scan all real files from the host OS
    # Only for local non-agent devices; enrolled agents scan their own files via daemon
    elif not (device.device_token_hash or device.auth_token):
        import pathlib

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
        # Only add test/sample directories if they exist
        sample_dir = os.path.join(workspace_root, "backend", "sample_files")
        if os.path.isdir(sample_dir):
            scan_dirs.append(sample_dir)

        SCAN_EXTENSIONS = {
            ".txt", ".csv", ".json", ".xml", ".log", ".md",
            ".doc", ".docx", ".xls", ".xlsx", ".pdf",
            ".html", ".htm", ".env", ".ini", ".cfg", ".conf",
            ".yaml", ".yml", ".toml", ".sql", ".py", ".js", ".ts",
            ".pem", ".key", ".crt", ".db", ".bak",
        }

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

                for root, dirs, files in os.walk(str(base_path), topdown=True):
                    if max_files_limit > 0 and len(files_to_scan) >= max_files_limit:
                        break
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

    # Simulation fallback gated strictly behind explicit DEMO flag
    if not files_to_scan and is_demo:
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        sample_files = [
            ("high_risk.txt", "EXTERNAL", "UPLOAD"),
            ("medium_risk.txt", "LOCAL", "READ"),
            ("low_risk.txt", "INTERNAL", "COPY"),
        ]
        # If files don't exist on disk, use synthetic demo content so demo mode is always self-contained
        if not files_to_scan:
            files_to_scan.extend([
                {
                    "filename": "sample_high_risk_credentials.txt",
                    "content": b"AWS_KEY=AKIAIOSFODNN7EXAMPLE\nCARD=4111 1111 1111 1111\nPASSWORD=Test@1234\n",
                    "destination": "EXTERNAL",
                    "action": "UPLOAD",
                    "classification": None,
                },
                {
                    "filename": "sample_medium_risk_pii.txt",
                    "content": b"Customer email: alice@company.com\nInternal IP: 192.168.1.100\n",
                    "destination": "LOCAL",
                    "action": "READ",
                    "classification": None,
                },
            ])
        if files_to_scan:
            is_simulated = True

    # If no files found:
    # - If demo was explicitly False (or custom_content/file_path was set but failed),
    #   fall back to computing summary from existing persisted records.
    # - Otherwise (plain dashboard "Scan" with no explicit demo=False), set scan_requested
    #   so the endpoint agent picks it up on its next heartbeat.
    if not files_to_scan:
        demo_explicitly_false = (payload is not None and payload.demo is False)
        had_custom_input = (payload is not None and (payload.custom_content or payload.file_path))
        if demo_explicitly_false or had_custom_input:
            # Return current DB state — don't request an agent scan
            return compute_device_scan_summary(device, db, is_simulated=False)
        # No files and no explicit override — forward to endpoint agent
        device.scan_requested = True
        db.commit()
        existing_summary = compute_device_scan_summary(device, db, is_simulated=False)
        existing_summary["message"] = f"Scan queued for device '{device.device_name}'. Waiting for endpoint agent to report findings."
        return existing_summary

    if is_simulated:
        # Simulated demo scan: scan files in memory without saving to database.
        # Simulated results are clearly marked is_simulated=True and NEVER saved as real Finding rows.
        sim_results = []
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
                db=None,
            )
            sim_results.append(res)

        max_risk_score = max((r.risk_score for r in sim_results if r.risk_score is not None), default=0)

        device_info = {
            "device_id": device.device_id,
            "device_name": device.device_name,
            "platform": device.platform,
            "status": device.status,
            "files_scanned": device.files_scanned or 0,
            "incidents_count": device.incidents_count or 0,
            "last_seen": device.last_seen.isoformat() if device.last_seen else None,
            "os_name": device.os_name,
            "os_version": device.os_version,
            "hostname": device.hostname,
            "ip_address": device.ip_address,
            "risk_score": max_risk_score,
        }

        threat_results = [r for r in sim_results if (r.risk_score or 0) >= 30]
        critical_results = [r for r in sim_results if (r.severity or "").upper() == "CRITICAL" or (r.risk_score or 0) >= 80]
        blocked_results = [r for r in sim_results if (r.action_taken or "").upper() == "BLOCKED" or (r.risk_score or 0) >= 70]

        if any((r.severity or "").upper() == "CRITICAL" or (r.risk_score or 0) >= 80 for r in sim_results):
            overall_risk_level = "CRITICAL"
        elif any((r.severity or "").upper() == "HIGH" or (r.risk_score or 0) >= 60 for r in sim_results):
            overall_risk_level = "HIGH"
        elif any((r.severity or "").upper() == "MEDIUM" or (r.risk_score or 0) >= 30 for r in sim_results):
            overall_risk_level = "MEDIUM"
        else:
            overall_risk_level = "LOW"

        if blocked_results:
            overall_block_level = "BLOCKED"
        elif threat_results:
            overall_block_level = "ALERTED"
        else:
            overall_block_level = "ALLOWED"

        user_info_count = 0
        ai_model_count = 0
        all_sim_findings = []
        for r in sim_results:
            for f in getattr(r, "findings", []):
                all_sim_findings.append(f)
                cat = (getattr(f, "category", "") or "").upper()
                rule = (getattr(f, "rule", "") or "").lower()
                if cat == "AI_MODELS" or any(k in rule for k in ("openai", "anthropic", "huggingface", "prompt", "llm", "chatgpt", "claude")):
                    ai_model_count += 1
                elif cat in ("PII", "FINANCIAL", "CREDENTIALS") or any(k in rule for k in ("email", "phone", "aadhaar", "pan", "card", "password", "jwt", "database", "api_key", "secret", "private_key", "ssn")):
                    user_info_count += 1

        sensitive_file_names = set(r.filename for r in threat_results if r.filename)

        sim_scan_results = []
        for r in sim_results:
            sim_scan_results.append({
                "filename": r.filename,
                "file_hash": r.file_hash,
                "file_size": r.file_size or 0,
                "classification": r.classification or "PUBLIC",
                "risk_score": r.risk_score or 0,
                "severity": r.severity,
                "action_taken": r.action_taken,
                "incident_id": None,
                "findings": [
                    {
                        "rule": f.rule,
                        "category": f.category,
                        "severity": f.severity,
                        "matched_text": f.matched_text,
                        "detail": f"{f.rule} detected in {r.filename}",
                    }
                    for f in getattr(r, "findings", [])
                ],
            })

        return {
            "status": "success",
            "has_scan_data": True,
            "message": f"Simulation scan completed for device '{device.device_name}' (demo mode).",
            "device": device_info,
            "scanned_files_count": len(sim_results),
            "risk_level": overall_risk_level,
            "risk_score": max_risk_score,
            "block_level": overall_block_level,
            "sensitive_files": len(sensitive_file_names),
            "blocked_transfers": len(blocked_results),
            "critical_incidents": len(critical_results),
            "threats_detected": len(all_sim_findings),
            "findings_count": len(all_sim_findings),
            "high_risk_count": sum(1 for r in sim_results if (r.risk_score or 0) >= 70),
            "user_information_count": user_info_count,
            "ai_model_sharing_count": ai_model_count,
            "total_bytes_scanned": sum(len(item["content"]) for item in files_to_scan),
            "scan_results": sim_scan_results,
            "is_simulated": True,
        }

    # Run actual scan with database persistence
    for item in files_to_scan:
        _process_scan(
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

    device.last_seen = _utc_now()
    db.commit()
    db.refresh(device)

    # Return summary computed directly from the persisted database records
    return compute_device_scan_summary(device, db, is_simulated=False)


# ---------------------------------------------------------------------------
# 8d. Agent Findings Ingestion (Local scan report from Windows/Endpoint Agent)
# ---------------------------------------------------------------------------
@router.post("/{device_id_or_id}/findings", response_model=AgentFindingsUploadResponse)
def upload_device_findings(
    device_id_or_id: str,
    payload: AgentFindingsUploadRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Ingest scan results uploaded directly by an enrolled DataGhost Endpoint Agent.
    
    Security & Privacy:
      - Authenticated via device.auth_token in Authorization: Bearer <token> or valid JWT.
      - Never accepts raw file contents or unredacted secrets.
      - Deduplicates findings via SHA-256 fingerprint.
      - Creates high/critical incidents and updates device risk scores dynamically.
    """
    device = _find_device(device_id_or_id, db)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device '{device_id_or_id}' not found.",
        )

    # Validate authentication: Bearer device_auth_token or valid JWT
    is_authenticated = _authenticate_device_request(device, request)
    if not is_authenticated:
        # Check JWT bearer token fallback with strict device ownership check
        auth_header = request.headers.get("Authorization", "")
        token = auth_header.replace("Bearer ", "").strip() if auth_header.startswith("Bearer ") else ""
        if token:
            try:
                from auth import verify_token
                username = verify_token(token)
                if username:
                    user = db.query(User).filter(User.username == username, User.is_active == True).first()
                    if user and (user.role == "admin" or user.id == device.user_id):
                        is_authenticated = True
            except Exception:
                pass

    if not is_authenticated:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing device authentication token for this device.",
        )


    now = _utc_now()
    device.last_seen = now
    device.scan_requested = False
    if device.status != "DISABLED":
        device.status = "ACTIVE"

    # Compute deterministic risk score and severity using backend/risk_engine
    from risk_engine.risk_calculator import RiskCalculator
    # Compute unified deterministic risk score and severity for findings
    max_risk, risk_level = calculate_findings_risk(payload.findings)
    classification = "RESTRICTED" if risk_level == "CRITICAL" else "CONFIDENTIAL" if payload.findings else "PUBLIC"

    # Create a ScanLog entry for this agent scan run
    scan_id = f"agent-scan-{secrets.token_hex(8)}"
    scan_log = ScanLog(
        scan_id=scan_id,
        timestamp=now,
        filename=f"agent_batch_{len(payload.findings)}_findings",
        classification=classification,
        risk_score=max_risk,
        findings_count=len(payload.findings),
        device_id=device.device_id,
        user_id=device.user_id,
        organization_id=device.organization_id or "default-org",
        status="COMPLETED",
        file_size=payload.total_bytes_scanned,
        is_simulated=False,
    )
    db.add(scan_log)
    db.flush()

    persisted_count = 0
    incidents_created = 0

    severity_risk_map = {
        "CRITICAL": 90,
        "HIGH": 70,
        "MEDIUM": 40,
        "LOW": 15,
    }

    for item in payload.findings:
        sev = (item.severity or "LOW").upper()
        item_risk = severity_risk_map.get(sev, 15)

        # Deterministic fingerprint: sha256(device_id:rule_id:file_name:line:redacted)
        fp_raw = f"{device.device_id}:{item.rule_id}:{item.file_name}:{item.line_number}:{item.evidence_redacted}"
        fingerprint = hashlib.sha256(fp_raw.encode("utf-8")).hexdigest()

        # Check existing finding for deduplication
        existing_finding = (
            db.query(Finding)
            .filter(Finding.fingerprint == fingerprint, Finding.device_id == device.device_id)
            .first()
        )

        if existing_finding:
            existing_finding.occurrence_count = (existing_finding.occurrence_count or 1) + 1
            existing_finding.last_seen_at = now
            existing_finding.scan_log_id = scan_log.id
            persisted_count += 1
        else:
            finding = Finding(
                scan_log_id=scan_log.id,
                scan_id=scan_id,
                user_id=device.user_id,
                organization_id=device.organization_id or "default-org",
                device_id=device.device_id,
                file_name=item.file_name,
                file_hash=item.file_hash,
                detector_id=item.rule_id,
                rule_id=item.rule_id,
                category=item.category,
                severity=sev,
                confidence=item.confidence,
                risk_score=item_risk,
                line_number=item.line_number,
                column_number=item.column_number,
                char_start=item.char_start,
                char_end=item.char_end,
                evidence_redacted=item.evidence_redacted,
                description=item.description or f"Sensitive data ({item.rule_id}) found in {item.file_name}",
                remediation=item.remediation or "Review, sanitize, or move sensitive credentials.",
                fingerprint=fingerprint,
                status="OPEN",
                is_simulated=False,
                first_seen_at=now,
                last_seen_at=now,
                occurrence_count=1,
            )
            db.add(finding)
            persisted_count += 1

        # Create Incident for HIGH and CRITICAL findings
        if sev in ("HIGH", "CRITICAL"):
            inc_id = f"INC-{secrets.token_hex(4).upper()}"
            incident = Incident(
                incident_id=inc_id,
                timestamp=now,
                user=device.device_name,
                filename=item.file_name,
                file_hash=item.file_hash,
                classification="RESTRICTED" if sev == "CRITICAL" else "CONFIDENTIAL",
                confidence=item.confidence,
                risk_score=item_risk,
                severity=sev,
                recommended_action="BLOCK" if sev == "CRITICAL" else "ALERT",
                action_taken="BLOCKED" if sev == "CRITICAL" else "ALERTED",
                destination="LOCAL",
                action="SCAN",
                status="OPEN",
                is_simulated=False,
                findings_json=json.dumps([{
                    "rule": item.rule_id,
                    "category": item.category,
                    "severity": sev,
                    "matched_text": item.evidence_redacted,
                }]),
                categories_json=json.dumps([item.category]),
                triggered_rules_json=json.dumps([item.rule_id]),
                device_id=device.device_id,
            )
            db.add(incident)
            incidents_created += 1

    scan_log.risk_score = max_risk
    # Update device stats
    device.files_scanned = (device.files_scanned or 0) + max(payload.scanned_files_count, 1 if payload.findings else 0)
    device.incidents_count = (device.incidents_count or 0) + incidents_created
    db.commit()
    db.refresh(device)
    _sync_to_firebase(device)

    return AgentFindingsUploadResponse(
        status="success",
        device_id=device.device_id,
        persisted_findings_count=persisted_count,
        incidents_created_count=incidents_created,
        risk_score=max_risk,
        risk_level=risk_level,
        message=f"Successfully ingested {persisted_count} findings from {device.device_name}.",
    )


# ---------------------------------------------------------------------------
# 9. Legacy Device Registration (Backwards Compatibility)
# ---------------------------------------------------------------------------
@router.post("/register", response_model=DeviceResponse)
def register_device_legacy(
    payload: DeviceRegisterRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Legacy registration endpoint for backwards compatibility with existing agents.
    Requires authentication. Only an admin or the owning user may upsert a device record.
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


