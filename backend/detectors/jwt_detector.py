"""
DataGhost – JWT Detector (Phase 3).

Detects JWT-shaped tokens (eyJ…header.eyJ…payload.signature) and validates
their three-part base64url structure locally.

Security notes:
  - A detected JWT is NEVER used for application authentication.
  - The full token is NOT stored – only a redacted prefix is logged.
  - Decoding the payload for display purposes only (no signature verification).
  - A structurally valid JWT does not prove it is authentic or authorised.
"""
from __future__ import annotations

import base64
import json
import re
from typing import List, Optional

from detectors.base import BaseDetector, DetectorFinding, _line_col, _redact

# Matches eyJ…<b64url>.eyJ…<b64url>.<b64url> (three dot-separated base64url parts)
_JWT_RE = re.compile(
    r"eyJ[A-Za-z0-9_\-]{4,}\.[A-Za-z0-9_\-]{4,}\.[A-Za-z0-9_\-]{4,}"
)


def _b64url_decode(s: str) -> bytes:
    """Decode base64url with padding."""
    padding = 4 - len(s) % 4
    if padding < 4:
        s += "=" * padding
    return base64.urlsafe_b64decode(s)


def _validate_jwt_structure(token: str) -> tuple[bool, dict]:
    """
    Validate the three-part structure of a JWT locally.
    Returns (is_valid, payload_dict).
    NEVER validates the signature – we are not a JWT verifier.
    """
    parts = token.split(".")
    if len(parts) != 3:
        return False, {}
    try:
        header_bytes = _b64url_decode(parts[0])
        header = json.loads(header_bytes)
        if not isinstance(header, dict) or "alg" not in header:
            return False, {}
        payload_bytes = _b64url_decode(parts[1])
        payload = json.loads(payload_bytes)
        return True, payload if isinstance(payload, dict) else {}
    except Exception:
        return False, {}


class JWTDetector(BaseDetector):
    detector_id = "jwt"
    name = "JWT Token Detector"
    categories = ["CREDENTIALS"]

    def detect(
        self,
        text: str,
        filename: str = "",
        context: Optional[dict] = None,
    ) -> List[DetectorFinding]:
        findings: List[DetectorFinding] = []
        seen: set[int] = set()

        for m in _JWT_RE.finditer(text):
            if m.start() in seen:
                continue

            token = m.group(0)
            is_valid, _payload = _validate_jwt_structure(token)
            if not is_valid:
                continue  # skip JWT-shaped strings that don't parse

            seen.add(m.start())
            line, col = _line_col(text, m.start())

            # Redact: show only the first 10 chars of the header part
            header_part = token.split(".")[0]
            evidence = _redact(header_part, keep_prefix=6) + ".[REDACTED].[REDACTED]"

            findings.append(DetectorFinding(
                detector_id=self.detector_id,
                rule_name="jwt_token",
                category="CREDENTIALS",
                severity="CRITICAL",
                confidence=0.93,
                filename=filename,
                line_number=line,
                column_start=col,
                char_start=m.start(),
                char_end=m.end(),
                evidence=evidence,
            ))

        return findings
