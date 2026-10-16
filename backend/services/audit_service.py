"""
DataGhost – Audit Service.

Provides a safe, append-only audit logging helper that records security-relevant
events (scans, findings, incidents, auth) to the audit_logs table.

SECURITY:
  • Sensitive data (passwords, tokens, secret values) is NEVER logged.
  • The sanitize helper strips known sensitive keys before JSON serialization.
  • Audit records are append-only; no update or delete endpoints exist.
"""
import json
import logging
import re
from datetime import datetime, timezone
from typing import Optional, Any, Dict

from sqlalchemy.orm import Session

from models import AuditLog

logger = logging.getLogger(__name__)

# Keys that must be stripped from metadata before audit persistence.
_SENSITIVE_KEYS = re.compile(
    r"(password|secret|token|api_key|access_key|private_key|credentials|authorization|cookie)",
    re.IGNORECASE,
)


def _sanitize_metadata(metadata: Optional[Dict[str, Any]]) -> Optional[str]:
    """
    Strip sensitive keys from a metadata dict and serialize to JSON.
    Returns None if metadata is None or empty.
    """
    if not metadata:
        return None
    sanitized = {}
    for key, value in metadata.items():
        if _SENSITIVE_KEYS.search(key):
            sanitized[key] = "***REDACTED***"
        elif isinstance(value, str) and len(value) > 500:
            sanitized[key] = value[:500] + "…"
        else:
            sanitized[key] = value
    try:
        return json.dumps(sanitized, default=str)
    except (TypeError, ValueError):
        return json.dumps({"error": "metadata serialization failed"})


def log_audit_event(
    db: Session,
    action: str,
    resource_type: Optional[str] = None,
    actor_user_id: Optional[int] = None,
    actor_username: Optional[str] = None,
    organization_id: str = "default-org",
    resource_id: Optional[str] = None,
    result: str = "SUCCESS",
    ip_address: Optional[str] = None,
    request_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Optional[AuditLog]:
    """
    Persist a single audit event to the audit_logs table.

    This is designed to be non-fatal: if persistence fails, the error is
    logged but the calling operation is NOT aborted.
    """
    try:
        entry = AuditLog(
            actor_user_id=actor_user_id,
            actor_username=actor_username,
            organization_id=organization_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            result=result,
            ip_address=ip_address,
            request_id=request_id,
            metadata_json=_sanitize_metadata(metadata),
            created_at=datetime.now(timezone.utc),
        )
        db.add(entry)
        db.flush()  # get the id without committing (caller owns the transaction)
        return entry
    except Exception as exc:
        logger.warning("Audit log write failed (non-fatal): %s", exc)
        return None
