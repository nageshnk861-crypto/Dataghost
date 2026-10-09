"""
DataGhost – DLP rules catalogue endpoint.
GET /dlp-rules  → returns the live DLP rule definitions (no secrets, no patterns).
"""
from fastapi import APIRouter

from scanner.dlp_rules import DLP_RULES

router = APIRouter(prefix="/dlp-rules", tags=["dlp"])

# Human-readable descriptions for each rule name.
_DESCRIPTIONS: dict[str, str] = {
    "email_address":        "Detects email addresses in any format (user@domain.tld).",
    "phone_india":          "Detects 10-digit Indian mobile numbers starting with 6–9.",
    "aadhaar":              "Detects 12-digit Aadhaar numbers in space- or hyphen-separated format.",
    "pan_card":             "Detects Indian PAN card numbers (AAAAA0000A pattern).",
    "credit_card":          "Detects Visa, MasterCard, Amex, and Discover card numbers.",
    "bank_account":         "Detects 9–18 digit bank account numbers when financial context keywords are nearby.",
    "ifsc_code":            "Detects Indian bank IFSC codes (e.g. HDFC0001234).",
    "api_key_generic":      "Detects generic API keys assigned to common key-name patterns (api_key=, apiKey:).",
    "jwt_token":            "Detects JSON Web Tokens (three Base64url segments separated by dots).",
    "private_key":          "Detects RSA, EC, and OpenSSH private key PEM headers.",
    "aws_access_key":       "Detects AWS access key IDs starting with AKIA.",
    "google_api_key":       "Detects Google API keys starting with AIza.",
    "password_field":       "Detects password values assigned to common field names (password=, passwd=, pwd=).",
    "confidential_marker":  "Detects document classification labels such as CONFIDENTIAL, TOP SECRET, PROPRIETARY.",
    "employee_data_marker": "Detects payroll and HR keywords: salary, CTC, employee ID, payroll.",
    "customer_data_marker": "Detects CRM and customer data keywords: customer ID, client ID, account holder.",
}

# Map category to a recommended action.
_CATEGORY_ACTION: dict[str, str] = {
    "PII":         "ALERT",
    "FINANCIAL":   "BLOCK",
    "CREDENTIALS": "BLOCK",
    "CORPORATE":   "ALERT",
}

# Map severity to a risk-threshold label.
_SEVERITY_THRESHOLD: dict[str, str] = {
    "MEDIUM":   "≥ 30",
    "HIGH":     "≥ 60",
    "CRITICAL": "≥ 80",
    "LOW":      "≥ 10",
}


@router.get("", summary="List all active DLP rules")
def list_dlp_rules():
    """
    Returns the catalogue of active DLP detection rules.
    Each entry includes the rule name, category, severity, recommended action,
    risk threshold, and a human-readable description.
    No regex patterns are exposed.
    """
    result = []
    for rule in DLP_RULES:
        name = rule["name"]
        category = rule.get("category", "OTHER")
        severity = rule.get("severity", "MEDIUM")
        result.append({
            "name": name,
            "display_name": name.replace("_", " ").title(),
            "category": category,
            "severity": severity,
            "action": _CATEGORY_ACTION.get(category, "ALERT"),
            "risk_threshold": _SEVERITY_THRESHOLD.get(severity, "≥ 30"),
            "description": _DESCRIPTIONS.get(name, f"Detects {name.replace('_', ' ')} patterns."),
            "enabled": True,  # all rules are always active in this version
        })
    return result
