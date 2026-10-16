"""
DataGhost – Findings Management Routes.

Endpoints:
  GET   /findings          – paginated list of DLP findings with filters, search, sorting
  GET   /findings/stats    – aggregated findings statistics by severity, status, category
  GET   /findings/{id}     – retrieve a single finding by ID (IDOR protected)
  PATCH /findings/{id}     – update finding status (OPEN, ACKNOWLEDGED, RESOLVED, FALSE_POSITIVE)

RBAC:
  admin   → full visibility: access all findings across the organization.
  analyst → scoped visibility: access only findings linked to their user_id or owned devices.

SECURITY:
  • Auth is mandatory (get_current_user).
  • All evidence returned is pre-redacted; raw secrets are never exposed.
  • Status changes generate append-only audit log events.
"""
import math
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, func, desc, asc
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from models import Finding, User, Device
from schemas.schemas import (
    FindingResponse,
    FindingListResponse,
    FindingStatusUpdate,
    FindingStatsResponse,
)
from services.audit_service import log_audit_event

router = APIRouter(prefix="/findings", tags=["findings"])

ALLOWED_STATUSES = {"OPEN", "ACKNOWLEDGED", "RESOLVED", "FALSE_POSITIVE"}
ALLOWED_SEVERITIES = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}


def _apply_rbac_scope(query, current_user: User, db: Session):
    """
    Scope query according to user role:
      - admin: sees all findings
      - analyst: sees only findings matching user_id or devices owned by user
    """
    if current_user.role == "admin":
        return query

    # Analyst: find all devices belonging to this user
    user_devices = (
        db.query(Device.device_id)
        .filter(Device.user_id == current_user.id)
        .all()
    )
    device_ids = [d.device_id for d in user_devices if d.device_id]

    conditions = [Finding.user_id == current_user.id]
    if device_ids:
        conditions.append(Finding.device_id.in_(device_ids))

    return query.filter(or_(*conditions))


@router.get("", response_model=FindingListResponse, summary="List findings with pagination, filtering and sorting")
def list_findings(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status: OPEN, ACKNOWLEDGED, RESOLVED, FALSE_POSITIVE"),
    severity: Optional[str] = Query(None, description="Filter by severity: LOW, MEDIUM, HIGH, CRITICAL"),
    category: Optional[str] = Query(None, description="Filter by category e.g. CREDENTIALS, PII, FINANCIAL"),
    search: Optional[str] = Query(None, description="Search term for file_name, rule_id, or description"),
    scan_id: Optional[str] = Query(None, description="Filter by scan ID"),
    device_id: Optional[str] = Query(None, description="Filter by device ID"),
    date_from: Optional[str] = Query(None, description="ISO date string e.g. 2026-01-01"),
    date_to: Optional[str] = Query(None, description="ISO date string e.g. 2026-12-31"),
    sort_by: str = Query("created_at", description="Field to sort by: created_at, risk_score, severity, occurrence_count, last_seen_at"),
    sort_order: str = Query("desc", description="Sort order: asc or desc"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: Optional[int] = Query(None, ge=1, le=100, description="Items per page"),
    page_size: Optional[int] = Query(None, ge=1, le=100, description="Items per page (alias)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return a paginated list of persisted DLP findings with RBAC enforcement."""
    effective_per_page = per_page or page_size or 20

    q = db.query(Finding)
    q = _apply_rbac_scope(q, current_user, db)

    if status_filter:
        norm_status = status_filter.strip().upper()
        if norm_status in ALLOWED_STATUSES:
            q = q.filter(Finding.status == norm_status)

    if severity:
        norm_sev = severity.strip().upper()
        if norm_sev in ALLOWED_SEVERITIES:
            q = q.filter(Finding.severity == norm_sev)

    if category:
        q = q.filter(func.upper(Finding.category) == category.strip().upper())

    if search:
        search_pattern = f"%{search.strip()}%"
        q = q.filter(
            or_(
                Finding.file_name.ilike(search_pattern),
                Finding.rule_id.ilike(search_pattern),
                Finding.description.ilike(search_pattern),
                Finding.detector_id.ilike(search_pattern),
            )
        )

    if scan_id:
        q = q.filter(Finding.scan_id == scan_id.strip())

    if device_id:
        q = q.filter(Finding.device_id == device_id.strip())

    if date_from:
        try:
            dt_from = datetime.fromisoformat(date_from)
            q = q.filter(Finding.created_at >= dt_from)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date_from format. Use ISO format (YYYY-MM-DD).")

    if date_to:
        try:
            dt_to = datetime.fromisoformat(date_to)
            q = q.filter(Finding.created_at <= dt_to)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date_to format. Use ISO format (YYYY-MM-DD).")

    # Sorting
    sort_fields = {
        "created_at": Finding.created_at,
        "risk_score": Finding.risk_score,
        "severity": Finding.severity,
        "occurrence_count": Finding.occurrence_count,
        "last_seen_at": Finding.last_seen_at,
    }
    sort_column = sort_fields.get(sort_by.lower(), Finding.created_at)
    if sort_order.lower() == "asc":
        q = q.order_by(asc(sort_column))
    else:
        q = q.order_by(desc(sort_column))

    total = q.count()
    pages = math.ceil(total / effective_per_page) if total > 0 else 0
    items = q.offset((page - 1) * effective_per_page).limit(effective_per_page).all()

    return FindingListResponse(
        items=items,
        total=total,
        page=page,
        per_page=effective_per_page,
        pages=pages,
    )



@router.get("/stats", response_model=FindingStatsResponse, summary="Get aggregated finding statistics")
def get_finding_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return summary statistics of findings scoped to the current user's role."""
    base_q = db.query(Finding)
    base_q = _apply_rbac_scope(base_q, current_user, db)

    total = base_q.count()
    open_count = base_q.filter(Finding.status == "OPEN").count()
    ack_count = base_q.filter(Finding.status == "ACKNOWLEDGED").count()
    resolved_count = base_q.filter(Finding.status == "RESOLVED").count()
    fp_count = base_q.filter(Finding.status == "FALSE_POSITIVE").count()

    # By severity
    sev_counts = (
        base_q.with_entities(Finding.severity, func.count(Finding.id))
        .group_by(Finding.severity)
        .all()
    )
    by_severity = {sev: count for sev, count in sev_counts if sev}

    # By category
    cat_counts = (
        base_q.with_entities(Finding.category, func.count(Finding.id))
        .group_by(Finding.category)
        .all()
    )
    by_category = {cat: count for cat, count in cat_counts if cat}

    return FindingStatsResponse(
        total=total,
        open=open_count,
        acknowledged=ack_count,
        resolved=resolved_count,
        false_positive=fp_count,
        by_severity=by_severity,
        by_category=by_category,
    )


@router.get("/{finding_id}", response_model=FindingResponse, summary="Get finding detail by ID")
def get_finding(
    finding_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve details for a single finding with IDOR protection."""
    finding = db.query(Finding).filter(Finding.id == finding_id).first()
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found.")

    # IDOR check for analyst
    if current_user.role != "admin":
        user_devices = (
            db.query(Device.device_id)
            .filter(Device.user_id == current_user.id)
            .all()
        )
        allowed_device_ids = {d.device_id for d in user_devices if d.device_id}

        is_owner = (finding.user_id == current_user.id) or (finding.device_id in allowed_device_ids)
        if not is_owner:
            # 404 to avoid leaking existence of other users' findings
            raise HTTPException(status_code=404, detail="Finding not found.")

    return finding


@router.patch("/{finding_id}", response_model=FindingResponse, summary="Update finding status")
def update_finding_status(
    finding_id: int,
    payload: FindingStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update finding status with IDOR verification and audit trail logging.
    Allowed statuses: OPEN, ACKNOWLEDGED, RESOLVED, FALSE_POSITIVE.
    """
    norm_status = payload.status.strip().upper()
    if norm_status not in ALLOWED_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status '{payload.status}'. Allowed: {', '.join(sorted(ALLOWED_STATUSES))}",
        )

    finding = db.query(Finding).filter(Finding.id == finding_id).first()
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found.")

    # IDOR check for analyst
    if current_user.role != "admin":
        user_devices = (
            db.query(Device.device_id)
            .filter(Device.user_id == current_user.id)
            .all()
        )
        allowed_device_ids = {d.device_id for d in user_devices if d.device_id}

        is_owner = (finding.user_id == current_user.id) or (finding.device_id in allowed_device_ids)
        if not is_owner:
            raise HTTPException(status_code=404, detail="Finding not found.")

    old_status = finding.status
    finding.status = norm_status
    finding.updated_at = datetime.now(timezone.utc)

    # Security Audit Log
    log_audit_event(
        db=db,
        action="FINDING_STATUS_CHANGED",
        resource_type="FINDING",
        actor_user_id=current_user.id,
        actor_username=current_user.username,
        organization_id=finding.organization_id or "default-org",
        resource_id=str(finding.id),
        result="SUCCESS",
        metadata={
            "old_status": old_status,
            "new_status": norm_status,
            "comment": payload.comment,
            "fingerprint": finding.fingerprint,
            "rule_id": finding.rule_id,
            "category": finding.category,
        },
    )

    db.commit()
    db.refresh(finding)
    return finding
