"""
DataGhost – Password Detector (Phase 3).

Detects likely hardcoded passwords in configuration files, source code,
environment files, YAML/JSON/TOML, and connection strings.

Distinguishes between actual secret values and common placeholders.
Uses value-length and entropy heuristics to reduce false positives.
"""
from __future__ import annotations

import re
from typing import List, Optional

from detectors.base import (
    BaseDetector, DetectorFinding, _line_col, _redact, _is_placeholder, _has_high_entropy
)

# ─── Pattern ──────────────────────────────────────────────────────────────────
# Named groups: val_dq (double-quoted), val_sq (single-quoted), val_bare (unquoted)
_PASSWORD_RE = re.compile(
    r"""(?ix)
    # JSON double-quoted style: "password": "value"
    (?:
        "(?:[a-z0-9_]*_)?(?:password|passwd|secret|pwd|pass|credential|auth_pass|db_pass|api_pass)"
        \s*:\s*
        "(?P<val_dq>[^"]{4,})"
    )
    |
    # YAML/TOML single-quoted: password: 'value'
    (?:
        '(?:[a-z0-9_]*_)?(?:password|passwd|secret|pwd|pass)'
        \s*:\s*
        '(?P<val_sq>[^']{4,})'
    )
    |
    # env / config bare: PASSWORD=value or password: value
    (?:
        \b(?:[a-z0-9_]*_)?(?:password|passwd|secret|pwd|pass|credential|auth_pass|db_pass|api_pass)\b
        \s*(?:=|:)\s*
        (?:["'`]?)
        (?P<val_bare>\$\{[^}]+\}|[^\s"'`#,\]\}]{4,})
        (?:["'`])?
    )
    """,
)

_MIN_VALUE_LEN = 4


class PasswordDetector(BaseDetector):
    detector_id = "password"
    name = "Hardcoded Password Detector"
    categories = ["CREDENTIALS"]

    def detect(
        self,
        text: str,
        filename: str = "",
        context: Optional[dict] = None,
    ) -> List[DetectorFinding]:
        if not text or not isinstance(text, str):
            return []

        findings: List[DetectorFinding] = []
        seen: set[int] = set()

        for m in _PASSWORD_RE.finditer(text):
            if m.start() in seen:
                continue

            # Extract captured value from whichever group matched
            raw_value = (
                m.group("val_dq")
                or m.group("val_sq")
                or m.group("val_bare")
                or ""
            ).strip().strip("\"'`")

            if len(raw_value) < _MIN_VALUE_LEN:
                continue

            # Reject placeholders BEFORE anything else
            if _is_placeholder(raw_value):
                continue

            seen.add(m.start())
            line, col = _line_col(text, m.start())

            # Confidence: higher if high entropy
            conf = 0.85 if _has_high_entropy(raw_value, threshold=3.0, min_len=8) else 0.65

            # Build evidence: keep the key name, mask the value completely
            full_match = m.group(0)
            val_start_idx = full_match.find(raw_value)
            if val_start_idx >= 0:
                evidence = full_match[:val_start_idx] + _redact(raw_value, keep_prefix=0)
            else:
                evidence = full_match[:20] + _redact(raw_value, keep_prefix=0)

            findings.append(DetectorFinding(
                detector_id=self.detector_id,
                rule_name="hardcoded_password",
                category="CREDENTIALS",
                severity="HIGH",
                confidence=conf,
                filename=filename,
                line_number=line,
                column_start=col,
                char_start=m.start(),
                char_end=m.end(),
                evidence=evidence,
            ))

        return findings
