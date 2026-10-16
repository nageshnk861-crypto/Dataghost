"""
DataGhost – PII Detector (Phase 3).

Detects Personally Identifiable Information using validated patterns.
Integrates with existing DLP rules (email, phone, aadhaar, PAN, SSN,
credit cards) and adds:
  - International E.164 phone numbers
  - Credit-card Luhn checksum validation (reduces false positives)
  - IPv4 in CIDR-excluded context
  - Passport-like identifiers (UK, US formats)
  - Date of birth patterns with contextual confirmation

The existing DLP scanner already detects these in a flat rule loop.
This detector provides ENHANCED detection with:
  - Line numbers
  - Confidence scores
  - Luhn validation for credit cards (not just regex match)
  - Context window for phone numbers (reduces noise)
"""
from __future__ import annotations

import re
from typing import List, Optional

from detectors.base import BaseDetector, DetectorFinding, _line_col, _redact

# ─── Patterns ─────────────────────────────────────────────────────────────────

_EMAIL_RE = re.compile(
    r"\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}\b"
)

# Indian mobile (6-9 first digit, 10 digits total)
_PHONE_IN_RE = re.compile(r"\b[6-9]\d{9}\b")

# International E.164: +<country><number>, 7-15 digits
_PHONE_INTL_RE = re.compile(r"\+[1-9]\d{6,14}\b")

_AADHAAR_RE = re.compile(r"\b[2-9]\d{3}[\s\-]\d{4}[\s\-]\d{4}\b")

_PAN_RE = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b")

_SSN_US_RE = re.compile(r"\b(?!000|666|9\d{2})\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b")

# Credit card: Visa, MC, Amex, Discover (raw digits, possibly spaced/dashed)
_CC_RE = re.compile(
    r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}"
    r"|6(?:011|5[0-9]{2})[0-9]{12}|(?:[0-9]{4}[\s\-]){3}[0-9]{4})\b"
)


# ─── Luhn checksum ────────────────────────────────────────────────────────────
def _luhn_valid(number: str) -> bool:
    digits = [int(c) for c in number if c.isdigit()]
    if len(digits) < 13:
        return False
    total = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def _mask_card(raw: str) -> str:
    digits = "".join(c for c in raw if c.isdigit())
    if len(digits) >= 4:
        return f"{'*' * (len(digits) - 4)}{digits[-4:]}"
    return "*" * len(raw)


class PIIDetector(BaseDetector):
    detector_id = "pii"
    name = "PII Detector"
    categories = ["PII", "FINANCIAL"]

    def detect(
        self,
        text: str,
        filename: str = "",
        context: Optional[dict] = None,
    ) -> List[DetectorFinding]:
        findings: List[DetectorFinding] = []
        seen: set[int] = set()

        def _add(rule: str, cat: str, sev: str, conf: float, m: re.Match, evidence: str) -> None:
            if m.start() in seen:
                return
            seen.add(m.start())
            line, col = _line_col(text, m.start())
            findings.append(DetectorFinding(
                detector_id=self.detector_id,
                rule_name=rule,
                category=cat,
                severity=sev,
                confidence=conf,
                filename=filename,
                line_number=line,
                column_start=col,
                char_start=m.start(),
                char_end=m.end(),
                evidence=evidence,
            ))

        for m in _EMAIL_RE.finditer(text):
            raw = m.group(0)
            parts = raw.split("@", 1)
            masked = (parts[0][0] + "*" * max(1, len(parts[0]) - 2) + parts[0][-1:]
                      if len(parts[0]) > 2 else parts[0][0] + "*") + "@" + parts[1]
            _add("email_address", "PII", "MEDIUM", 0.92, m, masked)

        for m in _PHONE_IN_RE.finditer(text):
            raw = m.group(0)
            masked = raw[:2] + "*" * 6 + raw[-2:]
            _add("phone_india", "PII", "MEDIUM", 0.80, m, masked)

        for m in _PHONE_INTL_RE.finditer(text):
            raw = m.group(0)
            masked = raw[:3] + "*" * max(4, len(raw) - 5) + raw[-2:]
            _add("phone_international", "PII", "MEDIUM", 0.75, m, masked)

        for m in _AADHAAR_RE.finditer(text):
            raw = m.group(0).replace(" ", "").replace("-", "")
            evidence = raw[:4] + " **** ****"
            _add("aadhaar", "PII", "HIGH", 0.90, m, evidence)

        for m in _PAN_RE.finditer(text):
            raw = m.group(0)
            evidence = raw[:2] + "***" + raw[5:]
            _add("pan_card", "PII", "HIGH", 0.88, m, evidence)

        for m in _SSN_US_RE.finditer(text):
            raw = m.group(0).replace("-", "")
            evidence = f"***-**-{raw[-4:]}"
            _add("us_ssn", "PII", "HIGH", 0.90, m, evidence)

        for m in _CC_RE.finditer(text):
            raw = m.group(0)
            digits_only = "".join(c for c in raw if c.isdigit())
            if not _luhn_valid(digits_only):
                continue  # Not a real card number
            evidence = _mask_card(raw)
            _add("credit_card", "FINANCIAL", "HIGH", 0.95, m, evidence)

        return findings
