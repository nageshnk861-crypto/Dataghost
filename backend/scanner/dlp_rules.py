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


def luhn_checksum_valid(number_str: str) -> bool:
    """Validate numeric string using Luhn algorithm (Mod 10)."""
    digits = [int(c) for c in number_str if c.isdigit()]
    if len(digits) < 13 or len(digits) > 19:
        return False
    total = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


# ---------------------------------------------------------------------------
# Rule list
# ---------------------------------------------------------------------------
DLP_RULES: List[Dict[str, Any]] = [
    {
        "name": "credit_card",
        "pattern": _c(
            r"\b(?:4[0-9]{3}[-\s]?[0-9]{4}[-\s]?[0-9]{4}[-\s]?[0-9]{1,4}"
            r"|5[1-5][0-9]{2}[-\s]?[0-9]{4}[-\s]?[0-9]{4}[-\s]?[0-9]{4}"
            r"|3[47][0-9]{2}[-\s]?[0-9]{6}[-\s]?[0-9]{5}"
            r"|6(?:011|5[0-9]{2})[-\s]?[0-9]{4}[-\s]?[0-9]{4}[-\s]?[0-9]{4}"
            r"|4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}"
            r"|6(?:011|5[0-9]{2})[0-9]{12})\b"
        ),
        "severity": "HIGH",
        "category": "FINANCIAL",
        "validator": luhn_checksum_valid,
    },
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
            r"(?<!\d)[2-9]\d{3}[\s-]\d{4}[\s-]\d{4}(?!\d|[\s-]\d)"
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
    {
        "name": "us_ssn",
        "pattern": _c(r"\b(?!000|666|9\d{2})\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b"),
        "severity": "HIGH",
        "category": "PII",
    },
    {
        "name": "openai_api_key",
        "pattern": _c(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b"),
        "severity": "CRITICAL",
        "category": "AI_MODELS",
    },
    {
        "name": "anthropic_api_key",
        "pattern": _c(r"\bsk-ant-[A-Za-z0-9_-]{20,}\b"),
        "severity": "CRITICAL",
        "category": "AI_MODELS",
    },
    {
        "name": "huggingface_token",
        "pattern": _c(r"\bhf_[A-Za-z0-9]{34,}\b"),
        "severity": "CRITICAL",
        "category": "AI_MODELS",
    },
    {
        "name": "ai_prompt_sharing",
        "pattern": _c(
            r"\b(?:system prompt|you are a helpful ai|chatgpt prompt|openai completions|anthropic claude|share with ai|ai model training data|copilot prompt|feeding to gpt|input to llm)\b",
            re.IGNORECASE,
        ),
        "severity": "HIGH",
        "category": "AI_MODELS",
    },
    {
        "name": "ai_training_data_leak",
        "pattern": _c(
            r"\b(?:ai training dataset|fine-tuning data|llm training corpus|rlhf dataset)\b",
            re.IGNORECASE,
        ),
        "severity": "HIGH",
        "category": "AI_MODELS",
    },
    # ── 1. Personally Identifiable Information (PII) Extended ───────────────
    {
        "name": "passport_number",
        "pattern": _c(r"\b[A-PR-WYa-pr-wy][1-9]\d\s?\d{4}[1-9]\b"),
        "severity": "HIGH",
        "category": "PII",
        "context_keywords": ["passport", "republic", "travel document", "nationality"],
    },
    {
        "name": "driving_license",
        "pattern": _c(r"\b[A-Z]{2}[0-9]{2}[-\s]?[0-9]{11}\b"),
        "severity": "MEDIUM",
        "category": "PII",
        "context_keywords": ["dl", "driving", "licence", "license", "driver"],
    },
    {
        "name": "dob_marker",
        "pattern": _c(
            r"(?i)\b(?:dob|date\s*of\s*birth|birth\s*date)\s*[:=\s]+\s*([0-3]?[0-9][\/\-.][0-1]?[0-9][\/\-.](?:19|20)\d{2})\b"
        ),
        "severity": "MEDIUM",
        "category": "PII",
    },
    {
        "name": "pin_code",
        "pattern": _c(r"\b[1-9][0-9]{2}\s?[0-9]{3}\b"),
        "severity": "LOW",
        "category": "PII",
        "context_keywords": ["pincode", "pin code", "postal code", "zipcode", "zip code", "address"],
    },
    # ── 2. Payment & Financial Extended ─────────────────────────────────────
    {
        "name": "iban_code",
        "pattern": _c(r"\b[A-Z]{2}[0-9]{2}[A-Z0-9]{11,30}\b"),
        "severity": "HIGH",
        "category": "FINANCIAL",
        "context_keywords": ["iban", "bank", "wire", "transfer", "swift"],
    },
    {
        "name": "swift_bic",
        "pattern": _c(r"\b[A-Z]{6}[A-Z0-9]{2}(?:[A-Z0-9]{3})?\b"),
        "severity": "MEDIUM",
        "category": "FINANCIAL",
        "context_keywords": ["swift", "bic", "wire transfer", "bank code"],
    },
    {
        "name": "upi_id",
        "pattern": _c(
            r"\b[a-zA-Z0-9.\-_]{2,256}@(okhdfcbank|okaxis|oksbi|okicici|paytm|gpay|ybl|apl|upi)\b",
            re.IGNORECASE,
        ),
        "severity": "MEDIUM",
        "category": "FINANCIAL",
    },
    # ── 3 & 4. Authentication, Cloud & API Keys Extended ────────────────────
    {
        "name": "github_token",
        "pattern": _c(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{36,255}\b"),
        "severity": "CRITICAL",
        "category": "CREDENTIALS",
    },
    {
        "name": "slack_token",
        "pattern": _c(r"\bxox[baprs]-[0-9]{10,13}-[0-9]{10,13}[a-zA-Z0-9-]*\b"),
        "severity": "CRITICAL",
        "category": "CREDENTIALS",
    },
    {
        "name": "stripe_api_key",
        "pattern": _c(r"\b(?:sk|rk)_(?:live|test)_[0-9a-zA-Z]{24,}\b"),
        "severity": "CRITICAL",
        "category": "CREDENTIALS",
    },
    {
        "name": "ssh_private_key",
        "pattern": _c(r"-----BEGIN (?:OPENSSH|DSA|EC|RSA) PRIVATE KEY-----"),
        "severity": "CRITICAL",
        "category": "CREDENTIALS",
    },
    {
        "name": "authorization_header",
        "pattern": _c(
            r"(?i)\bauthorization\s*:\s*(?:bearer|basic)\s+([A-Za-z0-9_\-\.\+/=]{16,})"
        ),
        "severity": "CRITICAL",
        "category": "CREDENTIALS",
    },
    # ── 5. Database & Infrastructure Connection Strings ─────────────────────
    {
        "name": "database_connection_url",
        "pattern": _c(
            r"(?i)\b(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis|amqp|mssql)://[^\s:@]+:[^\s:@]+@[^\s/]+"
        ),
        "severity": "CRITICAL",
        "category": "DATABASE",
    },
    {
        "name": "k8s_secret_manifest",
        "pattern": _c(
            r"(?i)kind\s*:\s*Secret[\s\S]*?(?:data|stringData)\s*:"
        ),
        "severity": "HIGH",
        "category": "INFRASTRUCTURE",
    },
    # ── 8. Healthcare PHI Data ──────────────────────────────────────────────
    {
        "name": "healthcare_phi",
        "pattern": _c(
            r"(?i)\b(?:patient\s*(?:name|id|record)|medical\s*record|diagnosis|prescription|treatment\s*plan|insurance\s*member\s*id|phi)\s*[:=\s]+\s*([A-Za-z0-9\-\s]{3,40})\b"
        ),
        "severity": "HIGH",
        "category": "HEALTHCARE",
    },
]

# ---------------------------------------------------------------------------
# Quick lookup by name
# ---------------------------------------------------------------------------
DLP_RULES_BY_NAME: Dict[str, Dict[str, Any]] = {r["name"]: r for r in DLP_RULES}
