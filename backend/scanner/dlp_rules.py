"""
DataGhost – DLP rule definitions.
Each rule is a dict:
  name       – unique string identifier
  pattern    – compiled re.Pattern (or list of patterns)
  severity   – LOW | MEDIUM | HIGH | CRITICAL
  category   – PII | FINANCIAL | CREDENTIALS | CORPORATE
  context_keywords – optional list; rule only fires when at least one keyword
                     appears within 200 chars of the match (bank_account uses this).
"""
import re
from typing import List, Dict, Any

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------
def _c(pattern: str, flags: int = 0) -> re.Pattern:
    """Compile a regex with re.MULTILINE added by default."""
    return re.compile(pattern, flags | re.MULTILINE)


# ---------------------------------------------------------------------------
# Rule list
# ---------------------------------------------------------------------------
DLP_RULES: List[Dict[str, Any]] = [
    {
        "name": "email_address",
        "pattern": _c(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"),
        "severity": "MEDIUM",
        "category": "PII",
    },
    {
        "name": "phone_india",
        "pattern": _c(r"\b[6-9]\d{9}\b"),
        "severity": "MEDIUM",
        "category": "PII",
    },
    {
        "name": "aadhaar",
        "pattern": _c(
            r"\b[2-9]\d{3}\s\d{4}\s\d{4}\b|\b[2-9]\d{3}-\d{4}-\d{4}\b"
        ),
        "severity": "HIGH",
        "category": "PII",
    },
    {
        "name": "pan_card",
        "pattern": _c(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b"),
        "severity": "HIGH",
        "category": "PII",
    },
    {
        "name": "credit_card",
        "pattern": _c(
            r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}"
            r"|6(?:011|5[0-9]{2})[0-9]{12})\b"
        ),
        "severity": "HIGH",
        "category": "FINANCIAL",
    },
    {
        # bank_account: only fire when financial context keywords are nearby
        "name": "bank_account",
        "pattern": _c(r"\b[0-9]{9,18}\b"),
        "severity": "HIGH",
        "category": "FINANCIAL",
        "context_keywords": ["account", "acc", "acct", "bank", "ifsc", "iban", "neft", "rtgs"],
    },
    {
        "name": "ifsc_code",
        "pattern": _c(r"\b[A-Z]{4}0[A-Z0-9]{6}\b"),
        "severity": "MEDIUM",
        "category": "FINANCIAL",
    },
    {
        "name": "api_key_generic",
        "pattern": _c(
            r'(?:api[_\-]?key|apikey)\s*[=:\s]+\s*[\'"]?([A-Za-z0-9_\-]{32,})[\'"]?',
            re.IGNORECASE,
        ),
        "severity": "CRITICAL",
        "category": "CREDENTIALS",
    },
    {
        "name": "jwt_token",
        "pattern": _c(
            r"eyJ[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}"
        ),
        "severity": "CRITICAL",
        "category": "CREDENTIALS",
    },
    {
        "name": "private_key",
        "pattern": _c(r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"),
        "severity": "CRITICAL",
        "category": "CREDENTIALS",
    },
    {
        "name": "aws_access_key",
        "pattern": _c(r"\bAKIA[0-9A-Z]{16}\b"),
        "severity": "CRITICAL",
        "category": "CREDENTIALS",
    },
    {
        "name": "google_api_key",
        "pattern": _c(r"\bAIza[0-9A-Za-z_\-]{35}\b"),
        "severity": "CRITICAL",
        "category": "CREDENTIALS",
    },
    {
        "name": "password_field",
        "pattern": _c(
            r"(?:password|passwd|pwd)\s*[=:\s]+\s*[\S]{4,}",
            re.IGNORECASE,
        ),
        "severity": "HIGH",
        "category": "CREDENTIALS",
    },
    {
        "name": "confidential_marker",
        "pattern": _c(
            r"\b(?:confidential|top secret|classified|do not distribute"
            r"|internal use only|proprietary)\b",
            re.IGNORECASE,
        ),
        "severity": "HIGH",
        "category": "CORPORATE",
    },
    {
        "name": "employee_data_marker",
        "pattern": _c(
            r"\b(?:employee id|emp id|staff id|payroll|salary|ctc|annual package)\b",
            re.IGNORECASE,
        ),
        "severity": "HIGH",
        "category": "CORPORATE",
    },
    {
        "name": "customer_data_marker",
        "pattern": _c(
            r"\b(?:customer id|client id|customer database|crm|account holder)\b",
            re.IGNORECASE,
        ),
        "severity": "HIGH",
        "category": "CORPORATE",
    },
]

# ---------------------------------------------------------------------------
# Quick lookup by name
# ---------------------------------------------------------------------------
DLP_RULES_BY_NAME: Dict[str, Dict[str, Any]] = {r["name"]: r for r in DLP_RULES}
