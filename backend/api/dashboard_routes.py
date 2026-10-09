"""
DataGhost – dashboard aggregation routes.

GET /dashboard/stats    – summary counts
GET /dashboard/activity – 7-day scan activity

RBAC:
  admin   → system-wide aggregated statistics (all devices, all incidents).
  analyst → scoped view: only their own organization's data. Returns real counts
            from the database filtered by organization_id = 'default-org' (the
            org every analyst belongs to until per-user org scoping is added).
            Admins receive full counts; analysts receive counts for their scope
            and a 'scope' field so the frontend can label data correctly.

SECURITY: Role is loaded from the database via get_current_user.
          The client cannot elevate privileges by modifying any request field.
"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from models import Device, Incident, ScanLog, User
from schemas.schemas import ActivityDataPoint, DashboardStats, ThreatItem

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _analyst_device_ids(db: Session) -> list[str]:
    """Return the list of device_ids that analysts are allowed to see.

    Access model: analysts may view all devices in 'default-org'.
    Admins bypass this function entirely and query all devices.
    """
    devices = (
        db.query(Device.device_id)
        .filter(Device.organization_id == "default-org")
        .all()
    )
    return [d.device_id for d in devices]


@router.get("/stats", response_model=DashboardStats)
def dashboard_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return aggregated statistics for the SOC dashboard.

    Admins receive system-wide counts. Analysts receive counts scoped
    to the 'default-org' organization and their permitted devices.
    The 'scope' field in the response indicates the data boundary.
    """
    is_admin = current_user.role == "admin"

    if is_admin:
        # Admin: full system-wide view
        protected_devices = db.query(Device).filter(Device.status == "ACTIVE").count()
        files_scanned = db.query(func.sum(Device.files_scanned)).scalar() or 0

        sensitive_files = (
            db.query(ScanLog)
            .filter(ScanLog.risk_score >= 30)
            .count()
        )

        blocked_transfers = (
            db.query(Incident)
            .filter(Incident.action_taken == "BLOCKED")
            .count()
        )

        critical_incidents = (
            db.query(Incident)
            .filter(Incident.severity == "CRITICAL")
            .count()
        )

        top_incidents = (
            db.query(Incident)
            .order_by(Incident.risk_score.desc())
            .limit(5)
            .all()
        )

    else:
        # Analyst: scoped to default-org devices only
        allowed_device_ids = _analyst_device_ids(db)

        protected_devices = (
            db.query(Device)
            .filter(
                Device.status == "ACTIVE",
                Device.organization_id == "default-org",
            )
            .count()
        )

        files_scanned = (
            db.query(func.sum(Device.files_scanned))
            .filter(Device.organization_id == "default-org")
            .scalar()
            or 0
        )

        if allowed_device_ids:
            sensitive_files = (
                db.query(ScanLog)
                .filter(
                    ScanLog.risk_score >= 30,
                    ScanLog.device_id.in_(allowed_device_ids),
                )
                .count()
            )

            blocked_transfers = (
                db.query(Incident)
                .filter(
                    Incident.action_taken == "BLOCKED",
                    Incident.device_id.in_(allowed_device_ids),
                )
                .count()
            )

            critical_incidents = (
                db.query(Incident)
                .filter(
                    Incident.severity == "CRITICAL",
                    Incident.device_id.in_(allowed_device_ids),
                )
                .count()
            )

            top_incidents = (
                db.query(Incident)
                .filter(Incident.device_id.in_(allowed_device_ids))
                .order_by(Incident.risk_score.desc())
                .limit(5)
                .all()
            )
        else:
            sensitive_files = 0
            blocked_transfers = 0
            critical_incidents = 0
            top_incidents = []

    recent_threats = [
        ThreatItem(
            label=inc.filename or inc.incident_id,
            score=inc.risk_score,
            incident_id=inc.incident_id or "",
            filename=inc.filename or inc.incident_id or "",
            risk_score=inc.risk_score,
            severity=inc.severity,
            user=inc.user or "unknown",
            timestamp=inc.timestamp.isoformat() if inc.timestamp else "",
            action_taken=inc.action_taken or "",
        )
        for inc in top_incidents
    ]

    return DashboardStats(
        protected_devices=protected_devices,
        files_scanned=int(files_scanned),
        sensitive_files=sensitive_files,
        blocked_transfers=blocked_transfers,
        critical_incidents=critical_incidents,
        scope="all" if is_admin else "default-org",
        recent_threats=recent_threats,
    )


@router.get("/activity", response_model=list[ActivityDataPoint])
def dashboard_activity(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return per-day scan activity for the last 7 days.

    Admins see system-wide activity. Analysts see activity scoped to
    default-org devices only.
    """
    is_admin = current_user.role == "admin"
    allowed_device_ids = None if is_admin else _analyst_device_ids(db)

    today = datetime.utcnow().date()
    result = []

    for offset in range(6, -1, -1):
        day = today - timedelta(days=offset)
        day_start = datetime(day.year, day.month, day.day, 0, 0, 0)
        day_end = datetime(day.year, day.month, day.day, 23, 59, 59)

        scan_q = db.query(ScanLog).filter(
            ScanLog.timestamp >= day_start,
            ScanLog.timestamp <= day_end,
        )
        sensitive_q = db.query(ScanLog).filter(
            ScanLog.timestamp >= day_start,
            ScanLog.timestamp <= day_end,
            ScanLog.risk_score >= 30,
        )
        blocked_q = db.query(Incident).filter(
            Incident.timestamp >= day_start,
            Incident.timestamp <= day_end,
            Incident.action_taken == "BLOCKED",
        )

        if allowed_device_ids is not None:
            scan_q = scan_q.filter(ScanLog.device_id.in_(allowed_device_ids))
            sensitive_q = sensitive_q.filter(ScanLog.device_id.in_(allowed_device_ids))
            blocked_q = blocked_q.filter(Incident.device_id.in_(allowed_device_ids))

        result.append(
            ActivityDataPoint(
                date=day.strftime("%Y-%m-%d"),
                scans=scan_q.count(),
                sensitive=sensitive_q.count(),
                blocked=blocked_q.count(),
            )
        )

    return result
