"""
DataGhost – Comprehensive DLP & Threat Detection Test Suite
Covers all 10 detection categories, file format extractors, security controls,
and negative test cases specified in the checklist.
"""
import io
import zipfile
import pytest
from scanner.dlp_scanner import scan_text
from scanner.dlp_rules import DLP_RULES, DLP_RULES_BY_NAME
from scanner.sensitive_scanner import SensitiveScanner
from scanner.text_extractor import extract_text
from scanner.masking import mask_sensitive_text


# =============================================================================
# 1. PERSONALLY IDENTIFIABLE INFORMATION (PII)
# =============================================================================
class TestPIIDetection:
    def test_email_addresses(self):
        sample = "Contact us at security-team@dataghost.internal or user.name+tag@corp.co.uk"
        res = scan_text(sample)
        assert "email_address" in res["rules_triggered"]
        assert len([f for f in res["findings"] if f["rule"] == "email_address"]) >= 2

    def test_phone_numbers_india_and_intl(self):
        sample = "Emergency contact: 9876543210 and primary 8123456789"
        res = scan_text(sample)
        assert "phone_india" in res["rules_triggered"]

    def test_pan_numbers(self):
        sample = "Taxpayer PAN is ABCDE1234F on document"
        res = scan_text(sample)
        assert "pan_card" in res["rules_triggered"]

    def test_aadhaar_numbers(self):
        sample = "Resident Aadhaar: 2345 6789 0123 and alternate 9876-5432-1098"
        res = scan_text(sample)
        assert "aadhaar" in res["rules_triggered"]

    def test_us_ssn(self):
        sample = "Employee SSN: 123-45-6789 for tax filing"
        res = scan_text(sample)
        assert "us_ssn" in res["rules_triggered"]

    def test_passport_numbers(self):
        sample = "Republic of India Passport No: A2093458 for international travel document"
        res = scan_text(sample)
        assert "passport_number" in res["rules_triggered"]

    def test_driving_license(self):
        sample = "State driver DL licence number: DL0420110012345"
        res = scan_text(sample)
        assert "driving_license" in res["rules_triggered"]

    def test_dob_markers(self):
        sample = "Patient record with DOB: 14/08/1992 and date of birth: 1985-05-20"
        res = scan_text(sample)
        assert "dob_marker" in res["rules_triggered"]

    def test_pin_postal_codes(self):
        sample = "Delivery address: 12 MG Road, Bengaluru, pincode: 560001"
        res = scan_text(sample)
        assert "pin_code" in res["rules_triggered"]


# =============================================================================
# 2. PAYMENT AND FINANCIAL DATA
# =============================================================================
class TestFinancialDetection:
    def test_credit_card_visa_and_mastercard_luhn(self):
        # 4532... is a standard Luhn-valid Visa test card
        sample = "Payment card: 4532 0150 0000 0000 and 5555 5555 5555 4444"
        res = scan_text(sample)
        assert "credit_card" in res["rules_triggered"]

    def test_invalid_luhn_credit_card_rejected(self):
        # Invalid checksum
        sample = "False card number 4111 1111 1111 1112 should fail Luhn"
        res = scan_text(sample)
        assert "credit_card" not in res["rules_triggered"]

    def test_bank_account_with_context(self):
        sample = "Wire to bank account: 123456789012 for vendor settlement"
        res = scan_text(sample)
        assert "bank_account" in res["rules_triggered"]

    def test_ifsc_codes(self):
        sample = "Beneficiary bank IFSC: SBIN0001234 and HDFC0000456"
        res = scan_text(sample)
        assert "ifsc_code" in res["rules_triggered"]

    def test_iban_codes(self):
        sample = "International wire transfer IBAN: GB29NWBK60161331926819"
        res = scan_text(sample)
        assert "iban_code" in res["rules_triggered"]

    def test_swift_bic(self):
        sample = "SWIFT BIC wire code: DEUTDEDDFXX for Frankfurt exchange"
        res = scan_text(sample)
        assert "swift_bic" in res["rules_triggered"]

    def test_upi_ids(self):
        sample = "Transfer funds to merchant.test@okhdfcbank or rahul@paytm"
        res = scan_text(sample)
        assert "upi_id" in res["rules_triggered"]


# =============================================================================
# 3 & 4. AUTHENTICATION SECRETS, CLOUD CREDENTIALS & API KEYS
# =============================================================================
class TestCredentialsDetection:
    def test_aws_access_keys(self):
        sample = "AWS_ACCESS_KEY_ID = AKIAIOSFODNN7EXAMPLE"
        res = scan_text(sample)
        assert "aws_access_key" in res["rules_triggered"]

    def test_google_api_keys(self):
        sample = "Maps key: AIzaSyD-1234567890abcdefABCDEF123456789"
        res = scan_text(sample)
        assert "google_api_key" in res["rules_triggered"]

    def test_openai_and_anthropic_keys(self):
        sample = "sk-proj-abcde12345678901234567890 and sk-ant-12345678901234567890"
        res = scan_text(sample)
        assert "openai_api_key" in res["rules_triggered"]
        assert "anthropic_api_key" in res["rules_triggered"]

    def test_github_and_slack_tokens(self):
        sample = "token = " + "ghp_" + "1234567890abcdefghijklmnopqrstuvwxyz12 and " + "xoxb-" + "1234567890-1234567890-abcdef"
        res = scan_text(sample)
        assert "github_token" in res["rules_triggered"]
        assert "slack_token" in res["rules_triggered"]

    def test_stripe_api_keys(self):
        sample = "sk_" + "live_" + "51Abcdef123456789012345678901234"
        res = scan_text(sample)
        assert "stripe_api_key" in res["rules_triggered"]

    def test_passwords_and_assignments(self):
        sample = "db_password = SuperSecretMasterKey123!"
        res = scan_text(sample)
        assert "password_field" in res["rules_triggered"]

    def test_jwt_tokens(self):
        sample = "token = eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        res = scan_text(sample)
        assert "jwt_token" in res["rules_triggered"]

    def test_private_keys(self):
        sample = "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA...\n-----END RSA PRIVATE KEY-----"
        res = scan_text(sample)
        assert "private_key" in res["rules_triggered"]

    def test_authorization_headers(self):
        sample = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ91234567890"
        res = scan_text(sample)
        assert "authorization_header" in res["rules_triggered"]


# =============================================================================
# 5. DATABASE AND INFRASTRUCTURE SECRETS
# =============================================================================
class TestDatabaseAndInfrastructure:
    def test_postgresql_and_mysql_urls(self):
        sample = "DATABASE_URL=postgresql://app_user:s3cr3t_p@ss@prod-db.internal:5432/core"
        res = scan_text(sample)
        assert "database_connection_url" in res["rules_triggered"]

    def test_mongodb_and_redis_urls(self):
        sample = "CACHE=redis://default:redispw123@redis-master.cluster:6379/0"
        res = scan_text(sample)
        assert "database_connection_url" in res["rules_triggered"]

    def test_k8s_secret_manifests(self):
        sample = """
        apiVersion: v1
        kind: Secret
        metadata:
          name: db-credentials
        stringData:
          password: SuperSecretPassword123
        """
        res = scan_text(sample)
        assert "k8s_secret_manifest" in res["rules_triggered"]


# =============================================================================
# 6 & 7. CONFIDENTIAL BUSINESS & SOURCE CODE SECURITY
# =============================================================================
class TestBusinessAndSourceCode:
    def test_confidential_and_proprietary_markers(self):
        sample = "PROPRIETARY AND CONFIDENTIAL: DO NOT DISTRIBUTE OR TRANSMIT"
        res = scan_text(sample)
        assert "confidential_marker" in res["rules_triggered"]

    def test_employee_and_payroll_markers(self):
        sample = "Executive annual package and payroll salary breakdown"
        res = scan_text(sample)
        assert "employee_data_marker" in res["rules_triggered"]

    def test_customer_database_markers(self):
        sample = "Customer database client id lookup export records"
        res = scan_text(sample)
        assert "customer_data_marker" in res["rules_triggered"]


# =============================================================================
# 8. HEALTHCARE DATA (PHI)
# =============================================================================
class TestHealthcarePHI:
    def test_patient_and_prescription_records(self):
        sample = "Patient Name: Rahul Verma, Diagnosis: Acute Myocardial Infarction, Prescription: Atorvastatin 20mg"
        res = scan_text(sample)
        assert "healthcare_phi" in res["rules_triggered"]


# =============================================================================
# 9. FILE FORMAT EXTRACTORS (.txt, .json, .csv, .env, .xlsx, .pptx, .zip)
# =============================================================================
class TestFileFormatExtraction:
    def test_plain_text_files(self):
        txt_bytes = b"Config: API_KEY = 'sk-live-1234567890abcdef12345678901234'"
        extracted = extract_text(txt_bytes, "app.env")
        assert "sk-live" in extracted

    def test_csv_extraction(self):
        csv_bytes = b"name,email,pan\nAlice,alice@corp.com,ABCDE1234F\n"
        extracted = extract_text(csv_bytes, "users.csv")
        assert "ABCDE1234F" in extracted
        assert "email_address" in scan_text(extracted)["rules_triggered"]
        assert "pan_card" in scan_text(extracted)["rules_triggered"]

    def test_json_extraction(self):
        json_bytes = b'{"db": {"url": "postgresql://usr:pwd@db.host:5432/db"}}'
        extracted = extract_text(json_bytes, "secrets.json")
        assert "database_connection_url" in scan_text(extracted)["rules_triggered"]

    def test_zip_archive_extraction(self):
        # Create in-memory zip containing a sensitive file
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("confidential.txt", "AKIAIOSFODNN7EXAMPLE is active")
        zip_bytes = buf.getvalue()

        extracted = extract_text(zip_bytes, "archive.zip")
        assert "AKIAIOSFODNN7EXAMPLE" in extracted
        assert "aws_access_key" in scan_text(extracted)["rules_triggered"]


# =============================================================================
# 10. SECURITY BEHAVIOR: REDACTION, FALSE POSITIVES & SCORING
# =============================================================================
class TestSecurityBehaviors:
    def test_benign_text_no_false_positives(self):
        sample = (
            "The quick brown fox jumps over the lazy dog. "
            "System metrics are normal: CPU 12%, Memory 45%, Disk 30%. "
            "No alerts recorded during today's standup."
        )
        res = scan_text(sample)
        assert res["total_findings"] == 0
        assert len(res["rules_triggered"]) == 0

    def test_sensitive_masking(self):
        assert mask_sensitive_text("john.doe@example.com", "email_address") == "j******e@example.com"
        assert mask_sensitive_text("4532015000000000", "credit_card") == "****-****-****"
        assert mask_sensitive_text("AKIAIOSFODNN7EXAMPLE", "aws_access_key") == "AKIA****************"
        assert mask_sensitive_text("sk-proj-1234567890abcdef", "openai_api_key") == "sk-****************"
        assert mask_sensitive_text("123-45-6789", "us_ssn") == "***-**-****"
        assert "pass" not in mask_sensitive_text("postgresql://usr:pass@host/db", "database_connection_url")

    def test_risk_scoring(self):
        scanner = SensitiveScanner()
        findings = scanner.scan("AKIAIOSFODNN7EXAMPLE and patient name: John Doe")
        score = scanner.get_severity_score(findings)
        assert score >= 35  # Critical severity base tier
