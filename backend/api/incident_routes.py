"""
DataGhost – Incident Management Routes.

GET    /incidents               – paginated list with optional filters
GET    /incidents/{incident_id} – single incident detail
PATCH  /incidents/{incident_id} – update incident status (OPEN, ACKNOWLEDGED, RESOLVED)
DELETE /incidents/{incident_id} – delete an incident (admin only)

RBAC:
  admin   → full access: list all incidents, view detail, update status, delete.
  analyst → read-only access: list/view incidents scoped to default-org devices.
            Analysts CANNOT delete incidents.

SECURITY: Auth is mandatory (get_current_user, not optional).
          Role is loaded from the database on every request.
"""
import json
import math
from datetime import datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from auth import get_current_user, require_admin
from database import get_db
from models import Device, Incident, User
from schemas.schemas import IncidentResponse, IncidentListResponse, IncidentStatusUpdate

router = APIRouter(prefix="/incidents", tags=["incidents"])

ALLOWED_STATUSES = {"OPEN", "ACKNOWLEDGED", "RESOLVED"}


def _allowed_device_ids_for_analyst(db: Session) -> List[str]:
    """Return device_ids visible to analyst role (default-org scope)."""
    devices = (
        db.query(Device.device_id)
        .filter(Device.organization_id == "default-org")
        .all()
    )
    return [d.device_id for d in devices]


def _to_incident_response(inc: Incident) -> IncidentResponse:
    """Helper to convert Incident ORM model into structured IncidentResponse."""
    categories = []
    if inc.categories_json:
        try:
            categories = json.loads(inc.categories_json)
        except Exception:
            categories = []

    triggered_rules = []
    if inc.triggered_rules_json:
        try:
            triggered_rules = json.loads(inc.triggered_rules_json)
        except Exception:
            triggered_rules = []

    # Fallback to parse categories / rules from findings_json if needed
    if (not categories or not triggered_rules) and inc.findings_json:
        try:
            findings = json.loads(inc.findings_json)
            if not categories:
                categories = sorted(list(set(f.get("category", "") for f in findings if f.get("category"))))
            if not triggered_rules:
                triggered_rules = sorted(list(set(f.get("rule", f.get("rule_name", "")) for f in findings if f.get("rule") or f.get("rule_name"))))
        except Exception:
            pass

    rec_action = inc.recommended_action
    if not rec_action:
        if inc.severity == "CRITICAL":
            rec_action = "BLOCK"
        elif inc.severity in ("MEDIUM", "HIGH"):
            rec_action = "ALERT"
        else:
            rec_action = "ALLOW"

    return IncidentResponse(
        id=inc.id,
        incident_id=inc.incident_id,
        timestamp=inc.timestamp,
        user=inc.user,
        filename=inc.filename,
        file_hash=inc.file_hash,
        classification=inc.classification,
        confidence=inc.confidence if inc.confidence is not None else 1.0,
        risk_score=inc.risk_score,
        severity=inc.severity,
        recommended_action=rec_action,
        action_taken=inc.action_taken,
        destination=inc.destination or "INTERNAL",
        action=inc.action or "READ",
        status=inc.status or "OPEN",
        categories=categories,
        triggered_rules=triggered_rules,
        findings_json=inc.findings_json,
        device_id=inc.device_id,
        created_at=inc.created_at or inc.timestamp,
        updated_at=inc.updated_at or inc.timestamp,
    )


@router.get("", response_model=IncidentListResponse, summary="List incidents with pagination and filters")
def list_incidents(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status: OPEN | ACKNOWLEDGED | RESOLVED"),
    severity: Optional[str] = Query(None, description="Filter by severity: LOW | MEDIUM | HIGH | CRITICAL"),
    classification: Optional[str] = Query(None, description="Filter by classification: PUBLIC | INTERNAL | CONFIDENTIAL | RESTRICTED"),
    destination: Optional[str] = Query(None, description="Filter by destination: LOCAL | INTERNAL | CLOUD | USB | EXTERNAL"),
    recommended_action: Optional[str] = Query(None, description="Filter by recommended action: ALLOW | ALERT | BLOCK"),
    date_from: Optional[str] = Query(None, description="ISO date string e.g. 2024-01-01"),
    date_to: Optional[str] = Query(None, description="ISO date string e.g. 2024-12-31"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, alias="page_size", description="Items per page"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return a paginated list of security incidents with rich filtering capabilities.

    Admins see all incidents. Analysts see only incidents from default-org devices.
    """
    q = db.query(Incident)

    # RBAC scope filter – applied BEFORE any user-supplied filters.
    if current_user.role != "admin":
        allowed_ids = _allowed_device_ids_for_analyst(db)
        if allowed_ids:
            q = q.filter(Incident.device_id.in_(allowed_ids))
        else:
            # Analyst has no accessible devices → return empty result set
            return IncidentListResponse(items=[], total=0, page=page, per_page=per_page, pages=0)

    if status_filter:
        norm_status = status_filter.strip().upper()
        if norm_status in ALLOWED_STATUSES:
            q = q.filter(Incident.status == norm_status)

    if severity:
        q = q.filter(Incident.severity == severity.strip().upper())

    if classification:
        q = q.filter(Incident.classification == classification.strip().upper())

    if destination:
        q = q.filter(Incident.destination == destination.strip().upper())

    if recommended_action:
        q = q.filter(Incident.recommended_action == recommended_action.strip().upper())

    if date_from:
        try:
            dt_from = datetime.fromisoformat(date_from)
            q = q.filter(Incident.timestamp >= dt_from)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date_from format. Use ISO format (YYYY-MM-DD).")

    if date_to:
        try:
            dt_to = datetime.fromisoformat(date_to)
            q = q.filter(Incident.timestamp <= dt_to)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date_to format. Use ISO format (YYYY-MM-DD).")

    total = q.count()
    raw_items = (
        q.order_by(Incident.timestamp.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    items = [_to_incident_response(inc) for inc in raw_items]

    return IncidentListResponse(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
        pages=math.ceil(total / per_page) if total else 0,
    )


@router.get("/{incident_id}", response_model=IncidentResponse, summary="Get single incident detail")
def get_incident(
    incident_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return details for a single incident by ID.

    Analysts can only view incidents belonging to their scoped devices.
    """
    incident = (
        db.query(Incident)
        .filter(Incident.incident_id == incident_id)
        .first()
    )
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident '{incident_id}' not found",
        )

    # RBAC: analysts may only access incidents for their allowed devices.
    if current_user.role != "admin":
        allowed_ids = _allowed_device_ids_for_analyst(db)
        if incident.device_id and incident.device_id not in allowed_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access to this incident is not permitted",
            )

    return _to_incident_response(incident)


@router.patch("/{incident_id}", response_model=IncidentResponse, summary="Update incident status")
def update_incident_status(
    incident_id: str,
    payload: IncidentStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update the status of an incident.
    Allowed statuses: OPEN, ACKNOWLEDGED, RESOLVED.
    Analysts may only update incidents within their scoped devices.
    """
    new_status = payload.status.strip().upper()
    if new_status not in ALLOWED_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status '{payload.status}'. Allowed statuses: {sorted(list(ALLOWED_STATUSES))}",
        )

    incident = (
        db.query(Incident)
        .filter(Incident.incident_id == incident_id)
        .first()
    )
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident '{incident_id}' not found",
        )

    # RBAC: analysts may only update incidents for their allowed devices.
    if current_user.role != "admin":
        allowed_ids = _allowed_device_ids_for_analyst(db)
        if incident.device_id and incident.device_id not in allowed_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access to this incident is not permitted",
            )

    incident.status = new_status
    incident.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(incident)

    return _to_incident_response(incident)


@router.delete("/{incident_id}", summary="Delete an incident (admin only)")
def delete_incident(
    incident_id: str,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Delete an incident record. Admin only."""
    incident = (
        db.query(Incident)
        .filter(Incident.incident_id == incident_id)
        .first()
    )
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident '{incident_id}' not found",
        )

    db.delete(incident)
    db.commit()
    return {"message": f"Incident '{incident_id}' deleted successfully", "incident_id": incident_id}
