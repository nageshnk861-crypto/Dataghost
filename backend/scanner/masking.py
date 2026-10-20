"""
DataGhost – Sensitive Data Masking Utility.
Masks sensitive strings (PII, Financial, Credentials) to ensure API responses
do not expose raw secrets unnecessarily.
"""


def mask_sensitive_text(text: str, rule_name: str = "") -> str:
    """
    Mask a sensitive matched string based on its rule type.

    Parameters:
        text (str): The raw matched text.
        rule_name (str): The DLP rule name (e.g. 'credit_card', 'email_address').

    Returns:
        str: The masked representation of the sensitive text.
    """
    if not text:
        return ""

    rule = (rule_name or "").lower()

    if rule == "email_address":
        if "@" in text:
            name, domain = text.split("@", 1)
            if len(name) <= 2:
                masked_name = name[0] + "*" if len(name) > 0 else "*"
            else:
                masked_name = name[0] + "*" * (len(name) - 2) + name[-1]
            return f"{masked_name}@{domain}"
        return text[0] + "*" * (len(text) - 1)

    elif rule == "phone_india":
        if len(text) >= 4:
            return text[:2] + "*" * (len(text) - 4) + text[-2:]
        return "*" * len(text)

    elif rule in ("credit_card", "bank_account", "pan_card", "aadhaar", "ifsc_code"):
        # Financial & Identity tokens: fully mask middle and end; no raw secret or last-4 digits
        return "****-****-****"

    elif rule == "us_ssn":
        return "***-**-****"

    elif rule in (
        "api_key_generic",
        "jwt_token",
        "private_key",
        "aws_access_key",
        "google_api_key",
        "openai_api_key",
        "anthropic_api_key",
        "huggingface_token",
        "password_field",
    ):
        # Credentials: keep short identifier prefix (e.g. AKIA or sk-) and mask everything else with fixed asterisks
        if text.startswith("AKIA"):
            return "AKIA****************"
        if text.startswith("sk-"):
            return "sk-****************"
        return "****************"

    elif rule in ("confidential_marker", "employee_data_marker", "customer_data_marker", "ai_prompt_sharing", "ai_training_data_leak"):
        # Corporate marker labels
        return text

    # Default fallback
    if len(text) > 4:
        return text[:2] + "*" * (len(text) - 4) + text[-2:]
    return "*" * len(text)
