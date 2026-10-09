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
        # Financial & Identity tokens: keep first 2 and last 2/4 characters
        compact = text.replace(" ", "").replace("-", "")
        if len(compact) > 6:
            visible_end = 4 if len(compact) >= 12 else 2
            visible_start = 2
            mask_len = len(compact) - visible_start - visible_end
            return compact[:visible_start] + ("*" * mask_len) + compact[-visible_end:]
        return text[:2] + "*" * max(1, len(text) - 2)

    elif rule in (
        "api_key_generic",
        "jwt_token",
        "private_key",
        "aws_access_key",
        "google_api_key",
        "password_field",
    ):
        # Credentials: keep short prefix (up to 4 chars) and mask all remaining chars
        if len(text) > 6:
            prefix = text[:4]
            mask_len = min(len(text) - 4, 16)
            return prefix + ("*" * mask_len)
        return "*" * len(text)

    elif rule in ("confidential_marker", "employee_data_marker", "customer_data_marker"):
        # Corporate marker labels
        return text

    # Default fallback
    if len(text) > 4:
        return text[:2] + "*" * (len(text) - 4) + text[-2:]
    return "*" * len(text)
