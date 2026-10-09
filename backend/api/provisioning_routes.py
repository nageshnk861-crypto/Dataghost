"""
DataGhost – Device Provisioning Admin API Routes.

Administrators create device provisioning records to enable zero-touch enrollment.
All endpoints require admin role and return hashed bootstrap tokens (never plaintext).

Routes:
  POST /device-provisioning/create    – Create provisioning record with bootstrap token
  GET  /device-provisioning/list      – List provisioning records
  GET  /device-provisioning/{id}      – Get specific provisioning record
  POST /device-provisioning/{id}/revoke – Revoke a provisioning record
"""
import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from models import DeviceProvisioning, User

logger = logging.getLogger("dataghost.provisioning")

router = APIRouter(prefix="/device-provisioning", tags=["provisioning"])


def _utc_now() -> datetime:
    """Return current UTC datetime."""
    return datetime.now(timezone.utc)


def _hash_token(raw_token: str) -> str:
    """Hash a raw token using SHA-256."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


# Pydantic request/response models
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


@router.post("/create", response_model=ProvisioningCreateResponse)
def create_device_provisioning(
    req: ProvisioningCreateRequest,
    authorization: Optional[str] = Header(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a device provisioning record for automated enrollment.
    
    ADMIN-ONLY endpoint. Administrators create provisioning records to enable
    zero-touch enrollment for organization-owned devices.
    
    Request body:
        {
            "organization_id": "org-123",
            "enrollment_policy_id": "policy-windows-corp",
            "platform": "Windows|Android|macOS|iOS",
            "provisioning_method": "AUTOMATIC_ENROLLMENT",
            "device_count": 10,
            "expiration_days": 30
        }
    
    Response:
        {
            "provisioning_id": 1,
            "organization_id": "org-123",
            "platform": "Windows",
            "status": "ACTIVE",
            "bootstrap_token": "dg_boot_xxxxxxxxxxxxxxxx",
            "expires_at": "2025-02-09T00:00:00Z"
        }
    
    The bootstrap token is returned ONCE. It must be securely transmitted to devices
    via MDM, enrollment configuration, or provisioning metadata. The token hash
    is stored in the database.
    """
    # RBAC: Only admins can create provisioning records
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can create provisioning records",
        )
    
    # Validate platform
    valid_platforms = {"Windows", "Android", "macOS", "iOS"}
    if req.platform not in valid_platforms:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid platform. Must be one of: {', '.join(valid_platforms)}",
        )
    
    # Generate secure bootstrap token (32+ bytes entropy)
    raw_token = secrets.token_urlsafe(32)
    token_hash = _hash_token(raw_token)
    
    # Calculate expiration
    now = _utc_now()
    expires_at = now + timedelta(days=req.expiration_days or 30)
    
    # Create provisioning record
    prov = DeviceProvisioning(
        organization_id=req.organization_id,
        enrollment_policy_id=req.enrollment_policy_id,
        platform=req.platform,
        status="ACTIVE",
        provisioning_method=req.provisioning_method,
        bootstrap_token_hash=token_hash,
        device_count=req.device_count or 1,
        created_by=current_user.username,
        expires_at=expires_at,
    )
    db.add(prov)
    db.commit()
    db.refresh(prov)
    
    logger.info(
        "Device provisioning record created: prov_id=%d, org_id=%s, platform=%s",
        prov.id,
        req.organization_id,
        req.platform,
    )
    
    return ProvisioningCreateResponse(
        provisioning_id=prov.id,
        organization_id=prov.organization_id,
        platform=prov.platform,
        status=prov.status,
        bootstrap_token=raw_token,  # Returned only once
        expires_at=expires_at.isoformat(),
    )


@router.get("/list")
def list_device_provisioning(
    organization_id: Optional[str] = None,
    platform: Optional[str] = None,
    status_filter: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List device provisioning records for an organization.
    
    ADMIN-ONLY endpoint. List all provisioning records created by administrators.
    
    Query params:
        organization_id: Filter by organization
        platform: Filter by platform (Windows, Android, macOS, iOS)
        status_filter: Filter by status (ACTIVE, REVOKED, EXPIRED)
    
    Response:
        [
            {
                "provisioning_id": 1,
                "organization_id": "org-123",
                "platform": "Windows",
                "status": "ACTIVE",
                "provisioning_method": "AUTOMATIC_ENROLLMENT",
                "device_count": 10,
                "created_at": "2025-01-09T00:00:00Z",
                "expires_at": "2025-02-09T00:00:00Z"
            },
            ...
        ]
    """
    # RBAC: Only admins can list provisioning records
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can list provisioning records",
        )
    
    # Build query
    query = db.query(DeviceProvisioning)
    
    if organization_id:
        query = query.filter(DeviceProvisioning.organization_id == organization_id)
    if platform:
        query = query.filter(DeviceProvisioning.platform == platform)
    if status_filter:
        query = query.filter(DeviceProvisioning.status == status_filter)
    
    records = query.order_by(DeviceProvisioning.created_at.desc()).all()
    
    return [
        ProvisioningListResponse(
            provisioning_id=r.id,
            organization_id=r.organization_id,
            platform=r.platform,
            status=r.status,
            provisioning_method=r.provisioning_method,
            device_count=r.device_count,
            created_at=r.created_at.isoformat(),
            expires_at=r.expires_at.isoformat() if r.expires_at else None,
        )
        for r in records
    ]


@router.get("/{provisioning_id}")
def get_device_provisioning(
    provisioning_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get a specific device provisioning record.
    
    ADMIN-ONLY endpoint. Retrieve details of a provisioning record by ID.
    """
    # RBAC: Only admins can view provisioning records
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can view provisioning records",
        )
    
    prov = db.query(DeviceProvisioning).filter(DeviceProvisioning.id == provisioning_id).first()
    if not prov:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Provisioning record {provisioning_id} not found",
        )
    
    # Ensure expires_at is timezone-aware
    expires_at = prov.expires_at
    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    
    created_at = prov.created_at
    if created_at and created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    
    last_used_at = prov.last_used_at
    if last_used_at and last_used_at.tzinfo is None:
        last_used_at = last_used_at.replace(tzinfo=timezone.utc)
    
    return ProvisioningStatusResponse(
        provisioning_id=prov.id,
        organization_id=prov.organization_id,
        platform=prov.platform,
        status=prov.status,
        provisioning_method=prov.provisioning_method,
        device_count=prov.device_count,
        created_by=prov.created_by,
        expires_at=expires_at.isoformat() if expires_at else None,
        created_at=created_at.isoformat(),
        last_used_at=last_used_at.isoformat() if last_used_at else None,
    )


@router.post("/{provisioning_id}/revoke")
def revoke_device_provisioning(
    provisioning_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Revoke a device provisioning record.
    
    ADMIN-ONLY endpoint. Prevent further enrollment using this provisioning record.
    """
    # RBAC: Only admins can revoke provisioning records
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can revoke provisioning records",
        )
    
    prov = db.query(DeviceProvisioning).filter(DeviceProvisioning.id == provisioning_id).first()
    if not prov:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Provisioning record {provisioning_id} not found",
        )
    
    prov.status = "REVOKED"
    prov.revoked_at = _utc_now()
    db.commit()
    
    logger.info(
        "Device provisioning record revoked: prov_id=%d, org_id=%s",
        provisioning_id,
        prov.organization_id,
    )
    
    return {"provisioning_id": provisioning_id, "status": "REVOKED"}


@router.get("")
def list_provisioning_by_org(
    organization_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List provisioning records for an organization.
    
    Query param: organization_id
    """
    # RBAC: Only admins can list provisioning records
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can list provisioning records",
        )
    
    records = db.query(DeviceProvisioning).filter(
        DeviceProvisioning.organization_id == organization_id
    ).order_by(DeviceProvisioning.created_at.desc()).all()
    
    return [
        ProvisioningListResponse(
            provisioning_id=r.id,
            organization_id=r.organization_id,
            platform=r.platform,
            status=r.status,
            provisioning_method=r.provisioning_method,
            device_count=r.device_count,
            created_at=r.created_at.isoformat(),
            expires_at=r.expires_at.isoformat() if r.expires_at else None,
        )
        for r in records
    ]
