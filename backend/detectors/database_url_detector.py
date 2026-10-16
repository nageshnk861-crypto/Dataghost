"""
DataGhost – Database URL Detector (Phase 3).

Detects database connection strings. Credentials are always redacted in
findings – passwords never appear in evidence snippets or logs.

Supported schemes:
  postgresql:// / postgres://
  mysql:// / mysql+pymysql:// / mariadb://
  mongodb:// / mongodb+srv://
  redis:// / rediss://
  mssql:// / sqlserver://
  oracle://
  sqlite:// (low severity – rarely contains credentials)
"""
from __future__ import annotations

import re
from typing import List, Optional
from urllib.parse import urlparse

from detectors.base import BaseDetector, DetectorFinding, _line_col

# One pattern that catches all db:// style URLs
_DB_URL_RE = re.compile(
    r"""(?:postgresql|postgres|mysql(?:\+\w+)?|mariadb|mongodb(?:\+srv)?"""
    r"""|redis[s]?|mssql(?:\+\w+)?|sqlserver|oracle|sqlite)://"""
    r"""[^\s"'`\[\]{}()<>\\]{4,}""",
    re.IGNORECASE,
)

# Scheme → severity
_SEVERITY: dict[str, str] = {
    "postgresql": "CRITICAL",
    "postgres":   "CRITICAL",
    "mysql":      "CRITICAL",
    "mariadb":    "CRITICAL",
    "mongodb":    "CRITICAL",
    "redis":      "HIGH",
    "rediss":     "HIGH",
    "mssql":      "CRITICAL",
    "sqlserver":  "CRITICAL",
    "oracle":     "CRITICAL",
    "sqlite":     "LOW",
}


def _redact_db_url(raw_url: str) -> str:
    """
    Replace any userinfo (user:password@) with <REDACTED>@ in the URL.
    Also redact query-string parameters that may contain credentials
    (password=, auth=, authSource=, etc.).
    """
    try:
        parsed = urlparse(raw_url)
        if parsed.password:
            # Rebuild without credentials
            netloc = f"<REDACTED>@{parsed.hostname}"
            if parsed.port:
                netloc += f":{parsed.port}"
            redacted = parsed._replace(netloc=netloc).geturl()
            return redacted
    except Exception:
        pass
    # Fallback: simple regex substitution
    redacted = re.sub(
        r"://[^@\s]+@",
        "://<REDACTED>@",
        raw_url,
        flags=re.IGNORECASE,
    )
    # Mask query-string credential params
    redacted = re.sub(
        r"(?<=\?|&)(?:password|passwd|pwd|auth|authsource)=[^&\s\"'`]+",
        r"password=<REDACTED>",
        redacted,
        flags=re.IGNORECASE,
    )
    return redacted


def _has_credentials(raw_url: str) -> bool:
    """Return True if URL appears to embed credentials."""
    try:
        p = urlparse(raw_url)
        if p.password:
            return True
    except Exception:
        pass
    return bool(re.search(r"://[^@/\s]+:[^@/\s]+@", raw_url))


class DatabaseURLDetector(BaseDetector):
    detector_id = "database_url"
    name = "Database URL Detector"
    categories = ["CREDENTIALS"]

    def detect(
        self,
        text: str,
        filename: str = "",
        context: Optional[dict] = None,
    ) -> List[DetectorFinding]:
        findings: List[DetectorFinding] = []
        seen: set[int] = set()

        for m in _DB_URL_RE.finditer(text):
            if m.start() in seen:
                continue
            seen.add(m.start())

            raw_url = m.group(0)
            scheme = raw_url.split("://", 1)[0].lower().split("+")[0]
            has_creds = _has_credentials(raw_url)

            # sqlite without credentials is informational only
            if scheme == "sqlite" and not has_creds:
                continue

            severity = _SEVERITY.get(scheme, "HIGH")
            # Downgrade severity if no credentials embedded
            if not has_creds and severity == "CRITICAL":
                severity = "HIGH"

            confidence = 0.95 if has_creds else 0.75
            evidence = _redact_db_url(raw_url)
            line, col = _line_col(text, m.start())

            findings.append(DetectorFinding(
                detector_id=self.detector_id,
                rule_name=f"database_url_{scheme}",
                category="CREDENTIALS",
                severity=severity,
                confidence=confidence,
                filename=filename,
                line_number=line,
                column_start=col,
                char_start=m.start(),
                char_end=m.end(),
                evidence=evidence,
            ))

        return findings
