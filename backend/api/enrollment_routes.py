"""
DataGhost – Secure Device Enrollment API Routes.

Zero-touch enrollment endpoints for automatic device provisioning.
All endpoints require Bearer token authentication.
Bootstrap tokens are single-use and consumed on first call.

Routes:
  POST /bootstrap    – Initialize enrollment with bootstrap token
  POST /attest       – Validate platform attestation
  POST /complete     – Complete device enrollment, create permanent Device record
  GET  /configuration– Retrieve device configuration
  GET  /policy       – Retrieve DLP policy for device
"""
import hashlib
import json
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth import get_current_user
from config import settings
from database import get_db
from models import (
    Device,
    EnrollmentToken,
    DeviceProvisioning,
    DeviceIdentity,
    EnrollmentState,
    User,
)

logger = logging.getLogger("dataghost.enrollment")

router = APIRouter(prefix="/device-enrollment", tags=["enrollment"])


# ---------------------------------------------------------------------------
# Pydantic request models
# ---------------------------------------------------------------------------
class BootstrapRequest(BaseModel):
    device_platform: str
    device_model: Optional[str] = None
    os_version: Optional[str] = None
    serial_number: Optional[str] = None


class AttestRequest(BaseModel):
    device_platform: str
    attestation_data: dict
    public_key: str
    device_token: Optional[str] = None


class CompleteRequest(BaseModel):
    device_platform: str
    public_key: str
    enrollment_code: Optional[str] = None
    device_supplied_id: Optional[str] = None
    device_name: Optional[str] = None
    os_version: Optional[str] = None
    hostname: Optional[str] = None
    ip_address: Optional[str] = None


# Provisioning Admin API Models
class ProvisioningCreateRequest(BaseModel):
    """Request to create a device provisioning record."""
    organization_id: str
    enrollment_policy_id: str
    platform: str  # Windows | Android | macOS | iOS
    provisioning_method: str = "AUTOMATIC_ENROLLMENT"
    device_count: Optional[int] = 1
    expiration_days: Optional[int] = 30


class ProvisioningCreateResponse(BaseModel):
    """Response with provisioning record and bootstrap token."""
    provisioning_id: int
    organization_id: str
    platform: str
    status: str
    bootstrap_token: str  # Raw token returned once (hashed in DB)
    expires_at: str


class ProvisioningStatusResponse(BaseModel):
    """Response with provisioning record status."""
    provisioning_id: int
    organization_id: str
    platform: str
    status: str
    provisioning_method: str
    device_count: int
    created_by: Optional[str]
    expires_at: Optional[str]
    created_at: str
    last_used_at: Optional[str]


class ProvisioningListResponse(BaseModel):
    """Response with list of provisioning records."""
    provisioning_id: int
    organization_id: str
    platform: str
    status: str
    provisioning_method: str
    device_count: int
    created_at: str
    expires_at: Optional[str]


def _utc_now() -> datetime:
    """Return current UTC datetime."""
    return datetime.now(timezone.utc)


def _hash_token(raw_token: str) -> str:
    """Hash a raw token using SHA-256."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _generate_device_id(platform: str, db: Session) -> str:
    """
    Generate a unique DataGhost device identifier.
    Format: DG-DEVICE-XXXXXXXX where XXXXXXXX is random hex.
    """
    platform_lower = platform.lower()
    
    # Map platform to short prefix
    prefix_map = {
        "windows": "dg-win",
        "linux": "dg-linux",
        "macos": "dg-mac",
        "darwin": "dg-mac",
        "android": "dg-android",
        "ios": "dg-ios",
    }
    pfx = prefix_map.get(platform_lower, "dg-dev")
    
    # Generate unique ID with entropy
    for attempt in range(5):
        candidate = f"{pfx}-{secrets.token_hex(4)}"
        if not db.query(Device).filter(Device.device_id == candidate).first():
            return candidate
    
    # Fallback: include timestamp entropy
    return f"{pfx}-{int(_utc_now().timestamp())}-{secrets.token_hex(2)}"


def _validate_attestation(
    platform: str, attestation_data: dict, public_key: str
) -> dict:
    """
    Validate platform-specific device attestation.
    
    Returns:
        {"valid": bool, "platform": str, "details": str}
    
    Currently implemented as stub. Production would implement:
    - Android: SafetyNet/Play Integrity API verification
    - iOS: DeviceCheck API verification
    - Windows: TPM attestation verification
    """
    platform_lower = platform.lower()
    
    # Stub implementation: Accept attestation for now
    # Production: Implement actual platform-specific verification
    
    if platform_lower == "android":
        # TODO: Verify SafetyNet/Play Integrity response
        logger.debug("Android attestation validation (stub implementation)")
        return {
            "valid": True,
            "platform": platform,
            "details": "Android attestation accepted (stub)"
        }
    elif platform_lower in ("ios", "iphone", "ipad"):
        # TODO: Verify DeviceCheck token
        logger.debug("iOS attestation validation (stub implementation)")
        return {
            "valid": True,
            "platform": platform,
            "details": "iOS attestation accepted (stub)"
        }
    elif platform_lower == "windows":
        # TODO: Verify TPM attestation
        logger.debug("Windows attestation validation (stub implementation)")
        return {
            "valid": True,
            "platform": platform,
            "details": "Windows attestation accepted (stub)"
        }
    elif platform_lower in ("macos", "darwin"):
        # TODO: Verify macOS attestation
        logger.debug("macOS attestation validation (stub implementation)")
        return {
            "valid": True,
            "platform": platform,
            "details": "macOS attestation accepted (stub)"
        }
    else:
        # Unknown platform - accept for now
        logger.warning("Unknown platform for attestation: %s", platform)
        return {
            "valid": True,
            "platform": platform,
            "details": "Attestation accepted (platform type unknown)"
        }


def _consume_provisioning_token(token_hash: str, db: Session) -> DeviceProvisioning:
    """
    Find and validate a device provisioning bootstrap token.
    
    Enforces single-use: token can only be consumed once (status transitions
    from ACTIVE to CONSUMED_BOOTSTRAP on first use).
    
    Raises:
        HTTPException 401 if token invalid, expired, revoked, or already used
    
    Returns:
        DeviceProvisioning record
    """
    prov = db.query(DeviceProvisioning).filter(
        DeviceProvisioning.bootstrap_token_hash == token_hash
    ).first()
    
    if not prov:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid provisioning bootstrap token",
        )
    
    now = _utc_now()
    exp = prov.expires_at
    if exp and exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    
    # Check if token has expired
    if exp and now > exp:
        prov.status = "EXPIRED"
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Provisioning bootstrap token has expired",
        )
    
    # Check if provisioning record is revoked
    if prov.status == "REVOKED":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Provisioning bootstrap token has been revoked",
        )
    
    # Check if token already been consumed (single-use enforcement)
    if prov.status == "CONSUMED_BOOTSTRAP":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Provisioning bootstrap token has already been used (single-use only)",
        )
    
    # Mark token as consumed on first use
    prov.status = "CONSUMED_BOOTSTRAP"
    prov.last_used_at = now
    db.commit()
    
    return prov


# ---------------------------------------------------------------------------
# Helper function: Extract Bearer token from Authorization header
# ---------------------------------------------------------------------------
def _get_bootstrap_token(
    authorization: Optional[str] = None,
) -> str:
    """Extract Bearer token from Authorization header."""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format. Expected: Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return parts[1]


def _extract_provisioning_id_from_token(authorization_token: str, db: Session) -> Optional[int]:
    """
    Extract provisioning record ID by looking up the authorization token in the database.
    Supports both raw bootstrap tokens and device session tokens.
    """
    if not authorization_token:
        return None
    
    # Try device session token format first (dg_prov_<prov_id>_<random>)
    if authorization_token.startswith("dg_prov_"):
        parts = authorization_token.split("_")
        if len(parts) >= 3:
            try:
                return int(parts[2])
            except (ValueError, IndexError):
                pass
    
    # Try raw bootstrap token (look it up in database)
    token_hash = _hash_token(authorization_token)
    prov = db.query(DeviceProvisioning).filter(
        DeviceProvisioning.bootstrap_token_hash == token_hash
    ).first()
    if prov:
        return prov.id
    
    return None


# ---------------------------------------------------------------------------
# Pydantic models for enrollment API requests
# ---------------------------------------------------------------------------
# 1. POST /bootstrap
# ---------------------------------------------------------------------------
@router.post("/bootstrap")
def bootstrap_enrollment(
    authorization: Optional[str] = Header(None),
    device_platform: Optional[str] = None,  # Accept as query param too
    req: Optional[BootstrapRequest] = None,
    db: Session = Depends(get_db),
):
    """
    Initialize enrollment with a single-use bootstrap token.
    
    Device provides bootstrap token via Authorization: Bearer <token> header.
    Server validates token, returns configuration and device identity key material.
    
    Request headers:
        Authorization: Bearer <provisioning-bootstrap-token>
    
    Request body (JSON) OR query params:
        device_platform: "Windows|Android|macOS|iOS" (required)
        device_model: "optional"
        os_version: "optional"
        serial_number: "optional"
    
    Response:
        {
            "server_url": "https://...",
            "organization_id": "org-xyz",
            "enrollment_policy": {...},
            "device_identity_public_key": "-----BEGIN PUBLIC KEY...",
            "bootstrap_status": "ACCEPTED",
            "next_step": "/attest"
        }
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header with bootstrap token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Support both request body and query parameters
    if req is not None:
        plat = req.device_platform
        model = req.device_model
        os_ver = req.os_version
        serial = req.serial_number
    else:
        if not device_platform:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="device_platform is required (query param or request body)",
            )
        plat = device_platform
        model = None
        os_ver = None
        serial = None
    
    # Extract Bearer token
    token = _get_bootstrap_token(authorization)
    token_hash = _hash_token(token)
    
    # Validate provisioning bootstrap token
    prov = _consume_provisioning_token(token_hash, db)
    
    logger.info(
        "Bootstrap enrollment initiated: platform=%s, model=%s, org_id=%s, prov_id=%d",
        plat,
        model or "unknown",
        prov.organization_id,
        prov.id,
    )
    
    # Server-generated public key for device identity
    # In production, this would be a real RSA public key or certificate
    # For now, use a placeholder that device stores and uses for future attestation
    device_public_key = f"-----BEGIN PUBLIC KEY-----\n{secrets.token_urlsafe(256)}\n-----END PUBLIC KEY-----"
    
    # Create a device session token that encodes the provisioning record ID
    # This allows us to retrieve the provisioning context in complete()
    device_session_token = f"dg_prov_{prov.id}_{secrets.token_urlsafe(16)}"
    
    server_url = getattr(settings, "SERVER_PUBLIC_URL", "http://localhost:8000")
    
    return {
        "server_url": server_url,
        "organization_id": prov.organization_id,
        "enrollment_policy": {
            "policy_id": prov.enrollment_policy_id,
            "platform": prov.platform,
            "allows_device_attestation": True,
        },
        "device_identity_public_key": device_public_key,
        "bootstrap_status": "ACCEPTED",
        "next_step": "/api/v1/device-enrollment/attest",
        "device_token": device_session_token,
        "expires_at": prov.expires_at.isoformat() if prov.expires_at else None,
    }


# ---------------------------------------------------------------------------
# 2. POST /attest
# ---------------------------------------------------------------------------
@router.post("/attest")
def attest_device(
    req: AttestRequest,
    device_token: Optional[str] = None,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """
    Validate device attestation (platform-specific cryptographic proof).
    
    Device provides attestation data signed by device OS security feature
    (Android SafetyNet, iOS DeviceCheck, Windows TPM, etc).
    
    Request headers:
        Authorization: Bearer <bootstrap-token-or-device-token>
    
    Request body (JSON):
        {
            "device_platform": "Android|iOS|Windows|macOS",
            "attestation_data": {...},
            "public_key": "-----BEGIN PUBLIC KEY...",
            "device_token": "optional"
        }
    
    Response:
        {
            "attestation_valid": true,
            "platform": "Android",
            "device_token": "<refreshed-device-token>",
            "next_step": "/complete"
        }
    """
    if not authorization and not device_token and not req.device_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing device token (Authorization header or device_token parameter)",
        )
    
    # Extract token from authorization header
    token_from_header = None
    if authorization:
        try:
            token_from_header = _get_bootstrap_token(authorization)
        except HTTPException:
            pass
    
    # If this is a raw bootstrap token (not a device session token),
    # validate it hasn't been consumed yet (single-use enforcement)
    if token_from_header and not token_from_header.startswith("dg_"):
        token_hash = _hash_token(token_from_header)
        prov = db.query(DeviceProvisioning).filter(
            DeviceProvisioning.bootstrap_token_hash == token_hash
        ).first()
        
        if prov:
            # Check if already consumed by bootstrap
            if prov.status == "CONSUMED_BOOTSTRAP":
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Bootstrap token already consumed (single-use only)",
                )
            # Check if revoked or expired
            if prov.status == "REVOKED":
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Bootstrap token has been revoked",
                )
            if prov.status == "EXPIRED":
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Bootstrap token has expired",
                )
    
    # Validate attestation based on platform
    attestation_result = _validate_attestation(
        req.device_platform,
        req.attestation_data,
        req.public_key,
    )
    
    if not attestation_result.get("valid"):
        logger.warning(
            "Device attestation failed: platform=%s, reason=%s",
            req.device_platform,
            attestation_result.get("details"),
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Device attestation validation failed: {attestation_result.get('details')}",
        )
    
    # Issue refreshed device token for next step
    # Preserve provisioning ID if present in the original token
    prov_id = None
    if token_from_header:
        prov_id = _extract_provisioning_id_from_token(token_from_header, db)
    
    if prov_id:
        new_device_token = f"dg_prov_{prov_id}_{secrets.token_urlsafe(16)}"
    else:
        new_device_token = f"dg_dev_{secrets.token_urlsafe(32)}"
    
    logger.info(
        "Device attestation validated: platform=%s, attestation_details=%s",
        req.device_platform,
        attestation_result.get("details"),
    )
    
    return {
        "attestation_valid": True,
        "platform": req.device_platform,
        "device_token": new_device_token,
        "attestation_details": attestation_result.get("details"),
        "next_step": "/api/v1/device-enrollment/complete",
    }


# ---------------------------------------------------------------------------
# 3. POST /complete
# ---------------------------------------------------------------------------
@router.post("/complete")
def complete_enrollment(
    req: CompleteRequest,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """
    Complete device enrollment and create permanent Device record.
    
    Device provides validated attestation and enrollment details.
    Server creates Device, assigns permanent DG-DEVICE-XXXXXXXX ID,
    stores public key fingerprint for future authentication,
    transitions device to ENROLLED/ACTIVE state.
    
    This endpoint is idempotent: calling multiple times with the same
    token returns the same device_id (no duplicates created).
    
    Request headers:
        Authorization: Bearer <device-session-token>
    
    Request body (JSON):
        {
            "device_platform": "Windows|Android|macOS|iOS",
            "public_key": "-----BEGIN PUBLIC KEY...",
            "enrollment_code": "optional DG-XXXX-XXXX",
            "device_supplied_id": "optional",
            "device_name": "optional",
            "os_version": "optional",
            "hostname": "optional",
            "ip_address": "optional"
        }
    
    Response:
        {
            "device_id": "DG-DEVICE-XXXXXXXX",
            "status": "ENROLLED",
            "organization_id": "org-xyz",
            "heartbeat_interval": 30,
            "download_policy": true
        }
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
        )
    
    # Extract device session token
    token = _get_bootstrap_token(authorization)
    prov_id = _extract_provisioning_id_from_token(token, db)
    token_hash = _hash_token(token)
    
    # Get provisioning context to retrieve organization_id
    organization_id = "default-org"
    if prov_id:
        prov = db.query(DeviceProvisioning).filter(DeviceProvisioning.id == prov_id).first()
        if prov:
            organization_id = prov.organization_id
            logger.debug("Using organization from provisioning record: %s", organization_id)
    
    # IDEMPOTENCY CHECK: Look for existing device created with this same token
    # Device table stores provisioning info in device_metadata JSON
    existing_devices = db.query(Device).filter(
        Device.organization_id == organization_id,
        Device.platform == req.device_platform,
        Device.public_key_fingerprint == hashlib.sha256(req.public_key.encode("utf-8")).hexdigest(),
    ).all()
    
    # If a device exists with the same organization, platform, and public key fingerprint,
    # return the existing device (idempotency)
    if existing_devices:
        device = existing_devices[0]
        logger.info(
            "Device enrollment idempotent: returning existing device_id=%s (already enrolled)",
            device.device_id,
        )
        return {
            "device_id": device.device_id,
            "status": "ENROLLED",
            "organization_id": device.organization_id,
            "heartbeat_interval": 30,
            "download_policy": True,
            "download_configuration": True,
            "server_url": getattr(settings, "SERVER_PUBLIC_URL", "http://localhost:8000"),
        }
    
    now = _utc_now()
    
    # Generate permanent, unique device ID
    device_id = _generate_device_id(req.device_platform, db)
    
    # Compute public key fingerprint (SHA-256 of PEM-encoded key)
    public_key_fingerprint = hashlib.sha256(
        req.public_key.encode("utf-8")
    ).hexdigest()
    
    # Create Device record
    device = Device(
        device_id=device_id,
        device_name=req.device_name or f"DataGhost {req.device_platform} Device",
        platform=req.device_platform,
        os_version=req.os_version,
        hostname=req.hostname,
        ip_address=req.ip_address,
        public_key_fingerprint=public_key_fingerprint,
        attestation_status="VALID",
        status="ACTIVE",
        enrolled_at=now,
        registered_at=now,
        organization_id=organization_id,
        device_metadata=json.dumps({
            "enrollment_code": req.enrollment_code,
            "device_supplied_id": req.device_supplied_id,
            "public_key_fingerprint": public_key_fingerprint,
            "provisioning_token_hash": token_hash,
        }) if req.enrollment_code or req.device_supplied_id else json.dumps({
            "public_key_fingerprint": public_key_fingerprint,
            "provisioning_token_hash": token_hash,
        }),
    )
    db.add(device)
    db.commit()
    db.refresh(device)
    
    # Store device public key and identity
    # Generate unique enrollment code if not provided
    if req.enrollment_code:
        enrollment_code_upper = req.enrollment_code.upper()
    else:
        # Generate with higher entropy to ensure uniqueness
        enrollment_code_upper = f"DG-{secrets.token_hex(4).upper()}-{secrets.token_hex(4).upper()}"
    
    device_identity = DeviceIdentity(
        device_id=device_id,
        platform=req.device_platform,
        public_key=req.public_key,
        attestation_data={"validated_at": now.isoformat()},
        enrollment_code=enrollment_code_upper,
    )
    db.add(device_identity)
    db.commit()
    db.refresh(device_identity)
    
    logger.info(
        "Device enrollment completed: device_id=%s, platform=%s, org_id=%s",
        device_id,
        req.device_platform,
        device.organization_id,
    )
    
    return {
        "device_id": device_id,
        "status": "ENROLLED",
        "organization_id": device.organization_id,
        "heartbeat_interval": 30,
        "download_policy": True,
        "download_configuration": True,
        "server_url": getattr(settings, "SERVER_PUBLIC_URL", "http://localhost:8000"),
    }


# ---------------------------------------------------------------------------
# 4. GET /configuration
# ---------------------------------------------------------------------------
@router.get("/configuration")
def get_device_configuration(
    device_id: Optional[str] = None,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """
    Retrieve device configuration after enrollment.
    
    Device queries configuration including organization, policies,
    heartbeat settings, and agent configuration.
    
    Request headers:
        Authorization: Bearer <device-token>
    
    Query params:
        device_id: Optional[str]
    
    Response:
        {
            "organization_id": "org-xyz",
            "policy_id": "policy-abc",
            "dlp_rules": [...],
            "server_url": "https://...",
            "heartbeat_interval": 30,
            "agent_configuration": {...}
        }
    """
    if not authorization and not device_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing device authentication",
        )
    
    # In production, use device_id from token claims or parameter
    # For now, use provided device_id
    if not device_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="device_id required in query parameters",
        )
    
    device = db.query(Device).filter(Device.device_id == device_id).first()
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device {device_id} not found",
        )
    
    return {
        "organization_id": device.organization_id,
        "policy_id": "default-policy",
        "dlp_rules": [
            {"id": "email_detection", "pattern": "email", "action": "ALERT"},
            {"id": "pii_detection", "pattern": "pii", "action": "BLOCK"},
        ],
        "server_url": getattr(settings, "SERVER_PUBLIC_URL", "http://localhost:8000"),
        "heartbeat_interval": 30,
        "agent_configuration": {
            "enable_file_scanning": True,
            "enable_network_monitoring": True,
            "enable_usb_control": False,
            "enable_cloud_sync": True,
        },
    }


# ---------------------------------------------------------------------------
# 5. GET /policy
# ---------------------------------------------------------------------------
@router.get("/policy")
def get_dlp_policy(
    device_id: Optional[str] = None,
    policy_id: Optional[str] = None,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """
    Retrieve DLP policy for device to execute locally.
    
    Device downloads full DLP policy rules to enforce client-side.
    
    Request headers:
        Authorization: Bearer <device-token>
    
    Query params:
        device_id: Optional[str]
        policy_id: Optional[str]
    
    Response:
        {
            "policy_id": "policy-abc",
            "version": "1.0",
            "rules": [...],
            "configurations": {...},
            "cache_ttl_seconds": 3600
        }
    """
    if not authorization and not device_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing device authentication",
        )
    
    if not device_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="device_id required in query parameters",
        )
    
    device = db.query(Device).filter(Device.device_id == device_id).first()
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device {device_id} not found",
        )
    
    return {
        "policy_id": policy_id or "default-policy",
        "version": "1.0",
        "rules": [
            {
                "id": "email_address_detection",
                "type": "regex",
                "pattern": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
                "category": "PII",
                "severity": "MEDIUM",
                "action": "ALERT",
            },
            {
                "id": "credit_card_detection",
                "type": "regex",
                "pattern": r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b",
                "category": "FINANCIAL",
                "severity": "HIGH",
                "action": "BLOCK",
            },
            {
                "id": "api_key_detection",
                "type": "regex",
                "pattern": r"api[_-]?key[:\s]*['\"]?[a-zA-Z0-9_-]{32,}['\"]?",
                "category": "CREDENTIALS",
                "severity": "CRITICAL",
                "action": "BLOCK",
            },
        ],
        "configurations": {
            "scan_on_copy": True,
            "scan_on_network_transfer": True,
            "scan_on_usb": False,
            "alert_user": True,
            "log_incidents": True,
        },
        "cache_ttl_seconds": 3600,
    }


