"""
Tests for DataGhost DLP Scanning Layer (Phase 1).
Validates all 16 DLP rules, context-awareness, finding structures, and false positive rejection.
All test credentials and PII samples are fake mock values.
"""
import pytest
from scanner.dlp_scanner import scan_text
from scanner.dlp_rules import DLP_RULES, DLP_RULES_BY_NAME
from scanner.sensitive_scanner import SensitiveScanner
from scanner.text_extractor import extract_text


# ---------------------------------------------------------------------------
# 1. Rule Catalog Verification
# ---------------------------------------------------------------------------

def test_rule_catalog_integrity():
    """Verify that all 16 rules are configured with expected severity and categories."""
    assert len(DLP_RULES) == 16
    assert len(DLP_RULES_BY_NAME) == 16

    expected_rules = {
        # PII
        "email_address": ("PII", "MEDIUM"),
        "phone_india": ("PII", "MEDIUM"),
        "aadhaar": ("PII", "HIGH"),
        "pan_card": ("PII", "HIGH"),
        # Financial
        "credit_card": ("FINANCIAL", "HIGH"),
        "bank_account": ("FINANCIAL", "HIGH"),
        "ifsc_code": ("FINANCIAL", "MEDIUM"),
        # Credentials
        "api_key_generic": ("CREDENTIALS", "CRITICAL"),
        "jwt_token": ("CREDENTIALS", "CRITICAL"),
        "private_key": ("CREDENTIALS", "CRITICAL"),
        "aws_access_key": ("CREDENTIALS", "CRITICAL"),
        "google_api_key": ("CREDENTIALS", "CRITICAL"),
        "password_field": ("CREDENTIALS", "HIGH"),
        # Corporate
        "confidential_marker": ("CORPORATE", "HIGH"),
        "employee_data_marker": ("CORPORATE", "HIGH"),
        "customer_data_marker": ("CORPORATE", "HIGH"),
    }

    for rule_name, (expected_cat, expected_sev) in expected_rules.items():
        assert rule_name in DLP_RULES_BY_NAME, f"Missing rule: {rule_name}"
        rule = DLP_RULES_BY_NAME[rule_name]
        assert rule["category"] == expected_cat
        assert rule["severity"] == expected_sev


# ---------------------------------------------------------------------------
# 2. PII Rules Tests
# ---------------------------------------------------------------------------

class TestPIIRules:
    def test_email_address(self):
        text = "Contact support at security-team.alerts@mock-domain.co.in for help."
        res = scan_text(text)
        assert "email_address" in res["rules_triggered"]
        finding = next(f for f in res["findings"] if f["rule"] == "email_address")
        assert finding["category"] == "PII"
        assert finding["severity"] == "MEDIUM"
        assert finding["matched_text"] == "security-team.alerts@mock-domain.co.in"
        assert text[finding["start"]:finding["end"]] == finding["matched_text"]

    def test_phone_india(self):
        text = "Direct call to mobile: 9876543210 or alternate 8123456789."
        res = scan_text(text)
        assert "phone_india" in res["rules_triggered"]
        phone_matches = [f["matched_text"] for f in res["findings"] if f["rule"] == "phone_india"]
        assert "9876543210" in phone_matches
        assert "8123456789" in phone_matches

    def test_phone_india_false_positive(self):
        # 10 digits not starting with 6-9 should NOT trigger phone_india
        text = "Tracking number: 1234567890 and timestamp code 5098765432."
        res = scan_text(text)
        assert "phone_india" not in res["rules_triggered"]

    def test_aadhaar(self):
        text_spaced = "UIDAI Aadhaar reference: 2345 6789 0123."
        res_spaced = scan_text(text_spaced)
        assert "aadhaar" in res_spaced["rules_triggered"]
        finding = next(f for f in res_spaced["findings"] if f["rule"] == "aadhaar")
        assert finding["matched_text"] == "2345 6789 0123"
        assert finding["severity"] == "HIGH"
        assert finding["category"] == "PII"

        text_hyphen = "UIDAI format: 9876-5432-1098."
        res_hyphen = scan_text(text_hyphen)
        assert "aadhaar" in res_hyphen["rules_triggered"]

    def test_aadhaar_false_positive(self):
        # Starts with 0 or 1 -> invalid Aadhaar format
        text = "Invalid ID: 0123 4567 8901 and 1234-5678-9012."
        res = scan_text(text)
        assert "aadhaar" not in res["rules_triggered"]

    def test_pan_card(self):
        text = "Tax identification PAN: ABCDE1234F is registered."
        res = scan_text(text)
        assert "pan_card" in res["rules_triggered"]
        finding = next(f for f in res["findings"] if f["rule"] == "pan_card")
        assert finding["matched_text"] == "ABCDE1234F"
        assert finding["severity"] == "HIGH"
        assert finding["category"] == "PII"

    def test_pan_card_false_positive(self):
        # Incorrect sequence of letters/digits
        text = "Code: 12345ABCDE and ABC12345DE and abcde1234f."
        res = scan_text(text)
        assert "pan_card" not in res["rules_triggered"]


# ---------------------------------------------------------------------------
# 3. Financial Rules Tests & Context Awareness
# ---------------------------------------------------------------------------

class TestFinancialRules:
    def test_credit_card(self):
        # Visa (16 digits)
        text_visa = "Payment card: 4111111111111111"
        res_visa = scan_text(text_visa)
        assert "credit_card" in res_visa["rules_triggered"]
        finding = next(f for f in res_visa["findings"] if f["rule"] == "credit_card")
        assert finding["category"] == "FINANCIAL"
        assert finding["severity"] == "HIGH"

        # Mastercard (16 digits)
        text_mc = "Card: 5500000000000004"
        assert "credit_card" in scan_text(text_mc)["rules_triggered"]

        # Amex (15 digits)
        text_amex = "Card: 378282246310005"
        assert "credit_card" in scan_text(text_amex)["rules_triggered"]

        # Discover (16 digits)
        text_disc = "Card: 6011000000000000"
        assert "credit_card" in scan_text(text_disc)["rules_triggered"]

    def test_bank_account_with_context(self):
        """Verify bank_account triggers when context keywords are within 200 chars."""
        context_samples = [
            ("Bank account number: 123456789012", "bank/account"),
            ("Transfer money to acc: 987654321012 immediately", "acc"),
            ("Beneficiary acct: 554433221100 for payroll", "acct"),
            ("National bank branch deposit 112233445566", "bank"),
            ("IFSC: SBIN0001234 Account: 998877665544", "ifsc"),
            ("Wire via IBAN details for 12345678901234", "iban"),
            ("Process NEFT settlement for 887766554433", "neft"),
            ("RTGS transaction to 776655443322 completed", "rtgs"),
        ]

        for text, desc in context_samples:
            res = scan_text(text)
            assert "bank_account" in res["rules_triggered"], f"Failed for context: {desc} in '{text}'"
            finding = next(f for f in res["findings"] if f["rule"] == "bank_account")
            assert finding["category"] == "FINANCIAL"
            assert finding["severity"] == "HIGH"

    def test_bank_account_false_positives_without_context(self):
        """A random 9-18 digit number without nearby financial context must NOT trigger bank_account."""
        non_context_samples = [
            "Order reference number: 123456789012",
            "Tracking ID: 98765432101234",
            "Warehouse package code: 554433221100",
            "Timestamp value 1700000000123 in audit log",
            "Serial number for component is 88776655443322",
        ]

        for text in non_context_samples:
            res = scan_text(text)
            assert "bank_account" not in res["rules_triggered"], f"False positive triggered for: '{text}'"

    def test_ifsc_code(self):
        text = "State Bank Branch IFSC: SBIN0001234 and HDFC0000123"
        res = scan_text(text)
        assert "ifsc_code" in res["rules_triggered"]
        matches = [f["matched_text"] for f in res["findings"] if f["rule"] == "ifsc_code"]
        assert "SBIN0001234" in matches
        assert "HDFC0000123" in matches

    def test_ifsc_code_false_positive(self):
        # 5th character must be 0
        text = "Invalid IFSC: SBIN1001234 and SBINX001234"
        res = scan_text(text)
        assert "ifsc_code" not in res["rules_triggered"]


# ---------------------------------------------------------------------------
# 4. Credentials Rules Tests
# ---------------------------------------------------------------------------

class TestCredentialsRules:
    def test_api_key_generic(self):
        text = "api_key = abcdef1234567890abcdef1234567890"
        res = scan_text(text)
        assert "api_key_generic" in res["rules_triggered"]
        finding = next(f for f in res["findings"] if f["rule"] == "api_key_generic")
        assert finding["category"] == "CREDENTIALS"
        assert finding["severity"] == "CRITICAL"

        text_alt = "apikey: '99887766554433221100aabbccddeeff'"
        assert "api_key_generic" in scan_text(text_alt)["rules_triggered"]

    def test_api_key_generic_false_positive(self):
        # Too short (<32 chars)
        text = "api_key = shortkey123"
        res = scan_text(text)
        assert "api_key_generic" not in res["rules_triggered"]

    def test_jwt_token(self):
        fake_jwt = (
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
            "eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIn0."
            "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        )
        text = f"Authorization: Bearer {fake_jwt}"
        res = scan_text(text)
        assert "jwt_token" in res["rules_triggered"]
        finding = next(f for f in res["findings"] if f["rule"] == "jwt_token")
        assert finding["category"] == "CREDENTIALS"
        assert finding["severity"] == "CRITICAL"

    def test_private_key(self):
        headers = [
            "-----BEGIN PRIVATE KEY-----",
            "-----BEGIN RSA PRIVATE KEY-----",
            "-----BEGIN EC PRIVATE KEY-----",
            "-----BEGIN OPENSSH PRIVATE KEY-----",
        ]
        for header in headers:
            text = f"{header}\nMIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQCfakekey...\n-----END PRIVATE KEY-----"
            res = scan_text(text)
            assert "private_key" in res["rules_triggered"], f"Failed for header: {header}"
            finding = next(f for f in res["findings"] if f["rule"] == "private_key")
            assert finding["category"] == "CREDENTIALS"
            assert finding["severity"] == "CRITICAL"

    def test_aws_access_key(self):
        fake_aws_key = "AKIAIOSFODNN7EXAMPLE"
        text = f"AWS credentials: aws_access_key_id = {fake_aws_key}"
        res = scan_text(text)
        assert "aws_access_key" in res["rules_triggered"]
        finding = next(f for f in res["findings"] if f["rule"] == "aws_access_key")
        assert finding["matched_text"] == fake_aws_key
        assert finding["category"] == "CREDENTIALS"
        assert finding["severity"] == "CRITICAL"

    def test_aws_access_key_false_positive(self):
        # Invalid prefix or length
        text = "Key: BKIAIOSFODNN7EXAMPLE and AKIA123SHORT"
        res = scan_text(text)
        assert "aws_access_key" not in res["rules_triggered"]

    def test_google_api_key(self):
        fake_gkey = "AIzaSyD-1234567890abcdefABCDEF123456789"
        text = f"Google Maps API key: {fake_gkey}"
        res = scan_text(text)
        assert "google_api_key" in res["rules_triggered"]
        finding = next(f for f in res["findings"] if f["rule"] == "google_api_key")
        assert finding["matched_text"] == fake_gkey
        assert finding["category"] == "CREDENTIALS"
        assert finding["severity"] == "CRITICAL"

    def test_google_api_key_false_positive(self):
        # Invalid prefix or length
        text = "Key: BIzaSyD-1234567890abcdef and AIzaShort"
        res = scan_text(text)
        assert "google_api_key" not in res["rules_triggered"]

    def test_password_field(self):
        samples = [
            "password = MockSecretPassword99!",
            "passwd: SecretPass123",
            "pwd = AdminP@ssw0rd",
        ]
        for text in samples:
            res = scan_text(text)
            assert "password_field" in res["rules_triggered"], f"Failed on '{text}'"
            finding = next(f for f in res["findings"] if f["rule"] == "password_field")
            assert finding["category"] == "CREDENTIALS"
            assert finding["severity"] == "HIGH"


# ---------------------------------------------------------------------------
# 5. Corporate Marker Rules Tests
# ---------------------------------------------------------------------------

class TestCorporateRules:
    def test_confidential_marker(self):
        markers = [
            "This document is CONFIDENTIAL",
            "Project status: TOP SECRET",
            "Handling instructions: CLASSIFIED",
            "Notice: DO NOT DISTRIBUTE",
            "FOR INTERNAL USE ONLY",
            "PROPRIETARY SOURCE CODE",
        ]
        for text in markers:
            res = scan_text(text)
            assert "confidential_marker" in res["rules_triggered"], f"Failed on '{text}'"
            finding = next(f for f in res["findings"] if f["rule"] == "confidential_marker")
            assert finding["category"] == "CORPORATE"
            assert finding["severity"] == "HIGH"

    def test_employee_data_marker(self):
        markers = [
            "Record: Employee ID: EMP-10928",
            "System Emp ID 44321",
            "Staff ID assigned: ST-902",
            "Monthly payroll run completed",
            "Salary structure details",
            "Offered CTC: 24 LPA",
            "Annual package details attached",
        ]
        for text in markers:
            res = scan_text(text)
            assert "employee_data_marker" in res["rules_triggered"], f"Failed on '{text}'"
            finding = next(f for f in res["findings"] if f["rule"] == "employee_data_marker")
            assert finding["category"] == "CORPORATE"
            assert finding["severity"] == "HIGH"

    def test_customer_data_marker(self):
        markers = [
            "Customer ID: CUST-88320",
            "Client ID: CL-7721",
            "Customer database backup file",
            "CRM export synchronized",
            "Account holder name on record",
        ]
        for text in markers:
            res = scan_text(text)
            assert "customer_data_marker" in res["rules_triggered"], f"Failed on '{text}'"
            finding = next(f for f in res["findings"] if f["rule"] == "customer_data_marker")
            assert finding["category"] == "CORPORATE"
            assert finding["severity"] == "HIGH"


# ---------------------------------------------------------------------------
# 6. Structured Output & Multi-finding Verification
# ---------------------------------------------------------------------------

class TestScannerOutputStructure:
    def test_structure_and_multi_findings(self):
        multi_text = """
        CONFIDENTIAL INTERNAL MEMO
        Employee ID: EMP-5541
        Contact: priya.nair@company.example.com
        Mobile: 9876543210
        PAN: ABCDE1234F
        Aadhaar: 3456 7890 1234
        Bank account number: 987654321098
        IFSC: SBIN0001234
        AWS Key: AKIAIOSFODNN7EXAMPLE
        """
        result = scan_text(multi_text)

        assert isinstance(result, dict)
        assert "findings" in result
        assert "total_findings" in result
        assert "rules_triggered" in result

        assert result["total_findings"] == len(result["findings"])
        assert result["total_findings"] >= 8

        # Verify all findings have the required schema fields
        for finding in result["findings"]:
            assert "rule" in finding
            assert "category" in finding
            assert "severity" in finding
            assert "start" in finding
            assert "end" in finding
            assert "matched_text" in finding

            assert finding["category"] in {"PII", "FINANCIAL", "CREDENTIALS", "CORPORATE"}
            assert finding["severity"] in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
            assert 0 <= finding["start"] < finding["end"] <= len(multi_text)
            assert multi_text[finding["start"]:finding["end"]] == finding["matched_text"]

        expected_triggered = {
            "confidential_marker",
            "employee_data_marker",
            "email_address",
            "phone_india",
            "pan_card",
            "aadhaar",
            "bank_account",
            "ifsc_code",
            "aws_access_key",
        }
        for rule_name in expected_triggered:
            assert rule_name in result["rules_triggered"]

    def test_empty_and_invalid_inputs(self):
        for empty_val in ["", None, "   \n\t  "]:
            res = scan_text(empty_val)
            if not empty_val or not isinstance(empty_val, str):
                assert res["findings"] == []
                assert res["total_findings"] == 0
                assert res["rules_triggered"] == []
            else:
                assert res["total_findings"] == 0

    def test_benign_clean_text(self):
        benign = "The annual technology conference will take place in the auditorium next Tuesday morning."
        res = scan_text(benign)
        assert res["total_findings"] == 0
        assert res["findings"] == []
        assert res["rules_triggered"] == []


# ---------------------------------------------------------------------------
# 7. SensitiveScanner and TextExtractor Integration
# ---------------------------------------------------------------------------

class TestSensitiveScannerAndExtractor:
    def test_sensitive_scanner_findings_and_severity(self):
        scanner = SensitiveScanner()
        text = """
        CONFIDENTIAL REPORT
        Email: test@example.com
        AWS Key: AKIAIOSFODNN7EXAMPLE
        """
        findings = scanner.scan(text)
        assert len(findings) >= 2

        score = scanner.get_severity_score(findings)
        assert 35 <= score <= 40  # CRITICAL tier base is 35-40

    def test_sensitive_scanner_bank_account_context(self):
        scanner = SensitiveScanner()

        # Should match with context
        with_context = "Bank account: 123456789012"
        findings_with = scanner.scan(with_context)
        assert any(f.rule_name == "bank_account" for f in findings_with)

        # Should not match without context
        without_context = "Order reference number: 123456789012"
        findings_without = scanner.scan(without_context)
        assert not any(f.rule_name == "bank_account" for f in findings_without)

    def test_text_extractor_plain_text(self):
        sample_bytes = b"Hello DataGhost DLP Scanner\nEmail: alert@example.com"
        extracted = extract_text(sample_bytes, "sample.txt")
        assert "Hello DataGhost" in extracted
        assert "alert@example.com" in extracted
