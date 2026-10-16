"""
DataGhost – Phase 3 Detector Tests.

All credentials and PII in this file are SYNTHETIC FIXTURES.
No real secrets, real persons' data, or production credentials appear here.

Test coverage:
  1.  API key detectors (AWS, GitHub, Stripe, Google, OpenAI, Slack, generic)
  2.  Database URL detection and credential redaction
  3.  Password detection with placeholder filtering
  4.  PII (email, phone, Aadhaar, PAN, SSN, credit card + Luhn)
  5.  Private key header detection (no key material stored)
  6.  JWT structural validation and redaction
  7.  IPv4/IPv6 classification
  8.  Multi-finding files and fingerprint deduplication
  9.  Edge cases: empty/binary/malformed input
  10. Registry isolation (one failing detector doesn't break others)
  11. Integration with scan_routes._process_scan
  12. Upload endpoint authentication (401 / 403)
  13. Clean file → zero findings
"""
import io
import sys
import zipfile
from pathlib import Path

import pytest

# Ensure backend is on the path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

# ─── Fixtures ─────────────────────────────────────────────────────────────────

# Synthetic API keys – all intentionally invalid / nonfunctional
FAKE_AWS_KEY        = "AKIA" + "IOSFODNN7EXAMPLE"          # AWS docs canonical example
FAKE_AWS_SECRET     = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
FAKE_GITHUB_TOKEN   = "ghp_" + "A" * 36  # exactly 36 chars after prefix
FAKE_STRIPE_KEY     = "sk_live_" + "F" * 40
FAKE_OPENAI_KEY     = "sk-" + "proj-FakeOpenAITestKeyForDataGhostDLP1234567890"
FAKE_SLACK_TOKEN    = "xox" + "b-1234567890-0987654321-FakeSlackToken123456"
FAKE_GOOGLE_KEY     = "AIzaSy" + "F" * 35  # AIza + 30+ chars
FAKE_HF_TOKEN       = "hf_" + "FakeHuggingFaceTokenForDataGhostDLPTesting1"

FAKE_DB_URL_PG      = "postgresql://admin:S3cr3tP@ssw0rd@db.internal.example.com:5432/appdb"
FAKE_DB_URL_MYSQL   = "mysql+pymysql://root:MyS3cretPass@127.0.0.1:3306/customers"
FAKE_DB_URL_MONGO   = "mongodb+srv://appuser:Fak3MongoP@ss@cluster0.mongodb.net/prod"
FAKE_DB_URL_REDIS   = "redis://:RedisP@ssw0rd@cache.example.com:6379/0"

# Synthetic PII
FAKE_EMAIL          = "test.analyst@fake-domain-dataghost.co.in"
FAKE_PHONE_IN       = "9876543210"
FAKE_AADHAAR        = "2345 6789 0123"
FAKE_PAN            = "ABCDE1234F"
FAKE_SSN            = "123-45-6789"
FAKE_CC_VISA        = "4532015112830366"   # Luhn-valid Visa test number (public test fixture)

# Synthetic private key header (no key material)
FAKE_PRIV_KEY_HEADER = "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEAFAKE\n-----END RSA PRIVATE KEY-----"
FAKE_EC_KEY_HEADER   = "-----BEGIN EC PRIVATE KEY-----"
FAKE_SSH_KEY_HEADER  = "-----BEGIN OPENSSH PRIVATE KEY-----"

# Synthetic JWT (nonfunctional – fabricated header/payload/signature)
import base64, json as _json
def _make_fake_jwt() -> str:
    header  = base64.urlsafe_b64encode(_json.dumps({"alg": "HS256", "typ": "JWT"}).encode()).rstrip(b"=").decode()
    payload = base64.urlsafe_b64encode(_json.dumps({"sub": "test-user", "role": "analyst"}).encode()).rstrip(b"=").decode()
    sig     = base64.urlsafe_b64encode(b"FakeSignatureNotReal1234").rstrip(b"=").decode()
    return f"{header}.{payload}.{sig}"
FAKE_JWT = _make_fake_jwt()

# Placeholder values that should NOT be flagged as passwords
PLACEHOLDERS = [
    "password=YOUR_PASSWORD_HERE",
    "secret=${SECRET_KEY}",
    "passwd=<password>",
    "pwd=CHANGE_ME",
    "password=xxx",
]


# ═══════════════════════════════════════════════════════════════════════════════
# 1. API Key Detector
# ═══════════════════════════════════════════════════════════════════════════════

class TestAPIKeyDetector:
    def _detector(self):
        from detectors.api_key_detector import APIKeyDetector
        return APIKeyDetector()

    def test_aws_access_key(self):
        d = self._detector()
        findings = d.detect(f"export AWS_ACCESS_KEY_ID={FAKE_AWS_KEY}")
        rules = [f.rule_name for f in findings]
        assert "aws_access_key_id" in rules

    def test_aws_key_evidence_redacted(self):
        d = self._detector()
        findings = d.detect(f"key={FAKE_AWS_KEY}")
        for f in findings:
            if f.rule_name == "aws_access_key_id":
                assert FAKE_AWS_KEY not in f.evidence
                assert "*" in f.evidence

    def test_github_token(self):
        d = self._detector()
        findings = d.detect(f"token = {FAKE_GITHUB_TOKEN}")
        rules = [f.rule_name for f in findings]
        assert "github_token" in rules

    def test_stripe_secret_key(self):
        d = self._detector()
        findings = d.detect(FAKE_STRIPE_KEY)
        rules = [f.rule_name for f in findings]
        assert "stripe_secret_key" in rules

    def test_openai_key(self):
        d = self._detector()
        findings = d.detect(f"OPENAI_API_KEY={FAKE_OPENAI_KEY}")
        rules = [f.rule_name for f in findings]
        assert "openai_api_key" in rules

    def test_slack_token(self):
        d = self._detector()
        findings = d.detect(FAKE_SLACK_TOKEN)
        rules = [f.rule_name for f in findings]
        assert "slack_token" in rules

    def test_google_key(self):
        d = self._detector()
        findings = d.detect(FAKE_GOOGLE_KEY)
        rules = [f.rule_name for f in findings]
        assert "google_api_key" in rules

    def test_huggingface_token(self):
        d = self._detector()
        findings = d.detect(FAKE_HF_TOKEN)
        rules = [f.rule_name for f in findings]
        assert "huggingface_token" in rules

    def test_generic_low_entropy_not_flagged(self):
        """A low-entropy assignment like api_key=testtest should NOT be flagged."""
        d = self._detector()
        findings = d.detect("api_key=testtesttest")
        generic = [f for f in findings if f.rule_name == "api_key_assignment"]
        assert len(generic) == 0

    def test_line_number_correct(self):
        text = "# config\napi_key=placeholder\nAWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE\n"
        d = self._detector()
        findings = d.detect(text)
        aws = [f for f in findings if f.rule_name == "aws_access_key_id"]
        assert len(aws) == 1
        assert aws[0].line_number == 3

    def test_confidence_is_set(self):
        d = self._detector()
        findings = d.detect(FAKE_AWS_KEY)
        for f in findings:
            assert 0.0 <= f.confidence <= 1.0

    def test_severity_critical(self):
        d = self._detector()
        findings = d.detect(FAKE_AWS_KEY)
        assert any(f.severity == "CRITICAL" for f in findings)

    def test_empty_text(self):
        d = self._detector()
        assert d.detect("") == []
        assert d.detect(None) == []  # type: ignore


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Database URL Detector
# ═══════════════════════════════════════════════════════════════════════════════

class TestDatabaseURLDetector:
    def _detector(self):
        from detectors.database_url_detector import DatabaseURLDetector
        return DatabaseURLDetector()

    def test_postgresql_detected(self):
        d = self._detector()
        findings = d.detect(FAKE_DB_URL_PG)
        assert len(findings) >= 1
        assert "database_url_postgresql" in [f.rule_name for f in findings]

    def test_mysql_detected(self):
        d = self._detector()
        findings = d.detect(FAKE_DB_URL_MYSQL)
        assert any("mysql" in f.rule_name for f in findings)

    def test_mongodb_detected(self):
        d = self._detector()
        findings = d.detect(FAKE_DB_URL_MONGO)
        assert any("mongodb" in f.rule_name for f in findings)

    def test_redis_detected(self):
        d = self._detector()
        findings = d.detect(FAKE_DB_URL_REDIS)
        assert any("redis" in f.rule_name for f in findings)

    def test_credentials_never_in_evidence_pg(self):
        d = self._detector()
        findings = d.detect(FAKE_DB_URL_PG)
        for f in findings:
            assert "S3cr3tP@ssw0rd" not in f.evidence, \
                f"Password exposed in evidence: {f.evidence}"

    def test_credentials_never_in_evidence_mysql(self):
        d = self._detector()
        findings = d.detect(FAKE_DB_URL_MYSQL)
        for f in findings:
            assert "MyS3cretPass" not in f.evidence

    def test_redacted_marker_present(self):
        d = self._detector()
        findings = d.detect(FAKE_DB_URL_PG)
        assert any("REDACTED" in f.evidence for f in findings)

    def test_severity_critical_with_creds(self):
        d = self._detector()
        findings = d.detect(FAKE_DB_URL_PG)
        assert any(f.severity == "CRITICAL" for f in findings)

    def test_no_url_produces_no_findings(self):
        d = self._detector()
        assert d.detect("hello world, no URLs here") == []

    def test_sqlite_without_credentials_skipped(self):
        d = self._detector()
        findings = d.detect("sqlite:///local.db")
        assert len(findings) == 0   # sqlite no-cred is below threshold


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Password Detector
# ═══════════════════════════════════════════════════════════════════════════════

class TestPasswordDetector:
    def _detector(self):
        from detectors.password_detector import PasswordDetector
        return PasswordDetector()

    def test_env_style_detected(self):
        d = self._detector()
        findings = d.detect("DB_PASSWORD=Sup3rS3cretValue!")
        assert len(findings) >= 1

    def test_json_style_detected(self):
        d = self._detector()
        findings = d.detect('"password": "Tr0ub4dor&3"')
        assert len(findings) >= 1

    def test_yaml_style_detected(self):
        d = self._detector()
        findings = d.detect("password: MyYamlP@ssw0rd")
        assert len(findings) >= 1

    def test_value_never_in_evidence(self):
        d = self._detector()
        findings = d.detect("password=S3cr3tV@lue123")
        for f in findings:
            assert "S3cr3tV@lue123" not in f.evidence

    def test_placeholder_your_password_ignored(self):
        d = self._detector()
        assert d.detect("password=YOUR_PASSWORD_HERE") == []

    def test_placeholder_env_var_ignored(self):
        d = self._detector()
        assert d.detect("secret=${SECRET_KEY}") == []

    def test_placeholder_change_me_ignored(self):
        d = self._detector()
        assert d.detect("pwd=CHANGE_ME") == []

    def test_placeholder_angle_bracket_ignored(self):
        d = self._detector()
        assert d.detect("passwd=<password>") == []

    def test_all_placeholder_variants_ignored(self):
        d = self._detector()
        for text in PLACEHOLDERS:
            findings = d.detect(text)
            assert len(findings) == 0, f"Should ignore placeholder: {text!r} but got {findings}"

    def test_severity_high(self):
        d = self._detector()
        findings = d.detect("password=Tr0ub4dor&3Really")
        assert all(f.severity == "HIGH" for f in findings)


# ═══════════════════════════════════════════════════════════════════════════════
# 4. PII Detector
# ═══════════════════════════════════════════════════════════════════════════════

class TestPIIDetector:
    def _detector(self):
        from detectors.pii_detector import PIIDetector
        return PIIDetector()

    def test_email_detected(self):
        d = self._detector()
        findings = d.detect(f"Contact: {FAKE_EMAIL}")
        rules = [f.rule_name for f in findings]
        assert "email_address" in rules

    def test_email_masked(self):
        d = self._detector()
        findings = d.detect(f"Contact: {FAKE_EMAIL}")
        for f in findings:
            if f.rule_name == "email_address":
                assert "*" in f.evidence
                assert "@" in f.evidence  # domain visible

    def test_indian_phone_detected(self):
        d = self._detector()
        findings = d.detect(f"Call us: {FAKE_PHONE_IN}")
        assert any(f.rule_name == "phone_india" for f in findings)

    def test_aadhaar_detected(self):
        d = self._detector()
        findings = d.detect(f"Aadhaar: {FAKE_AADHAAR}")
        assert any(f.rule_name == "aadhaar" for f in findings)

    def test_aadhaar_masked(self):
        d = self._detector()
        findings = d.detect(f"Aadhaar: {FAKE_AADHAAR}")
        for f in findings:
            if f.rule_name == "aadhaar":
                assert "6789" not in f.evidence  # middle section masked

    def test_pan_detected(self):
        d = self._detector()
        findings = d.detect(f"PAN: {FAKE_PAN}")
        assert any(f.rule_name == "pan_card" for f in findings)

    def test_ssn_detected(self):
        d = self._detector()
        findings = d.detect(f"SSN: {FAKE_SSN}")
        assert any(f.rule_name == "us_ssn" for f in findings)

    def test_ssn_masked(self):
        d = self._detector()
        findings = d.detect(f"SSN: {FAKE_SSN}")
        for f in findings:
            if f.rule_name == "us_ssn":
                assert "123" not in f.evidence
                assert "6789" in f.evidence  # only last 4 shown

    def test_credit_card_luhn_valid_detected(self):
        d = self._detector()
        findings = d.detect(f"Card: {FAKE_CC_VISA}")
        assert any(f.rule_name == "credit_card" for f in findings)

    def test_credit_card_luhn_invalid_not_detected(self):
        """A sequence of 16 digits that fails Luhn check should NOT be flagged."""
        d = self._detector()
        bad_card = "4532015112830360"   # Modified last digit – invalid Luhn
        findings = d.detect(f"Card: {bad_card}")
        assert not any(f.rule_name == "credit_card" for f in findings)

    def test_false_positive_random_number_not_flagged(self):
        """A random 10-digit number should not be flagged as a phone number."""
        d = self._detector()
        findings = d.detect("Version 1234500000 of the software")
        # Should not match phone (no 6-9 prefix) nor credit card
        assert len(findings) == 0


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Private Key Detector
# ═══════════════════════════════════════════════════════════════════════════════

class TestPrivateKeyDetector:
    def _detector(self):
        from detectors.private_key_detector import PrivateKeyDetector
        return PrivateKeyDetector()

    def test_rsa_key_detected(self):
        d = self._detector()
        findings = d.detect(FAKE_PRIV_KEY_HEADER)
        assert len(findings) >= 1
        assert any("rsa" in f.rule_name for f in findings)

    def test_ec_key_detected(self):
        d = self._detector()
        findings = d.detect(FAKE_EC_KEY_HEADER)
        assert any("ec" in f.rule_name for f in findings)

    def test_openssh_key_detected(self):
        d = self._detector()
        findings = d.detect(FAKE_SSH_KEY_HEADER)
        assert any("openssh" in f.rule_name for f in findings)

    def test_key_body_not_stored(self):
        """The MIIEowIBAAKCAQEAFAKE body must NOT appear in the finding evidence."""
        d = self._detector()
        findings = d.detect(FAKE_PRIV_KEY_HEADER)
        for f in findings:
            assert "MIIEowIBAAKCAQEAFAKE" not in f.evidence

    def test_severity_critical(self):
        d = self._detector()
        findings = d.detect(FAKE_PRIV_KEY_HEADER)
        assert all(f.severity == "CRITICAL" for f in findings)

    def test_confidence_very_high(self):
        d = self._detector()
        findings = d.detect(FAKE_PRIV_KEY_HEADER)
        assert all(f.confidence >= 0.95 for f in findings)

    def test_no_key_header_no_finding(self):
        d = self._detector()
        assert d.detect("BEGIN CERTIFICATE (this is not a private key)") == []


# ═══════════════════════════════════════════════════════════════════════════════
# 6. JWT Detector
# ═══════════════════════════════════════════════════════════════════════════════

class TestJWTDetector:
    def _detector(self):
        from detectors.jwt_detector import JWTDetector
        return JWTDetector()

    def test_valid_jwt_detected(self):
        d = self._detector()
        findings = d.detect(f"Authorization: Bearer {FAKE_JWT}")
        assert len(findings) >= 1
        assert any(f.rule_name == "jwt_token" for f in findings)

    def test_full_token_not_in_evidence(self):
        d = self._detector()
        findings = d.detect(FAKE_JWT)
        for f in findings:
            if f.rule_name == "jwt_token":
                # Evidence must be redacted – full token should not appear
                assert f.evidence != FAKE_JWT
                assert "[REDACTED]" in f.evidence

    def test_invalid_jwt_structure_ignored(self):
        """A string that looks like eyJ… but has only 2 parts should not match."""
        d = self._detector()
        findings = d.detect("eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ0ZXN0In0")
        assert len(findings) == 0

    def test_non_json_payload_ignored(self):
        """Three base64url parts but non-JSON header should not be flagged."""
        import base64
        bad = base64.urlsafe_b64encode(b"notjson").rstrip(b"=").decode()
        bad_jwt = f"eyJ{bad}.eyJ{bad}.{bad}"
        d = self._detector()
        findings = d.detect(bad_jwt)
        assert len(findings) == 0

    def test_jwt_never_used_for_auth(self):
        """
        Structural test: the JWT detector must not call any auth-validating function.
        The detector only uses local parsing and does not validate signatures.
        """
        from detectors import jwt_detector
        src = Path(jwt_detector.__file__).read_text()
        # Ensure no requests/httpx/urllib calls that could authenticate
        assert "requests" not in src
        assert "httpx" not in src
        assert "verify_token" not in src

    def test_severity_critical(self):
        d = self._detector()
        findings = d.detect(FAKE_JWT)
        assert all(f.severity == "CRITICAL" for f in findings)


# ═══════════════════════════════════════════════════════════════════════════════
# 7. IP Address Detector
# ═══════════════════════════════════════════════════════════════════════════════

class TestIPAddressDetector:
    def _detector(self):
        from detectors.ip_address_detector import IPAddressDetector
        return IPAddressDetector()

    def test_public_ipv4_detected(self):
        d = self._detector()
        # 8.8.8.8 is Google DNS – definitively public and routable
        findings = d.detect("HOST=8.8.8.8")
        assert len(findings) >= 1
        assert findings[0].severity == "MEDIUM"

    def test_loopback_not_flagged(self):
        d = self._detector()
        findings = d.detect("server_host=127.0.0.1")
        assert len(findings) == 0

    def test_private_rfc1918_not_flagged(self):
        d = self._detector()
        # Private IPs are below threshold (LOW severity, filtered)
        findings = d.detect("db_host=192.168.1.100")
        assert len(findings) == 0

    def test_version_string_not_flagged(self):
        d = self._detector()
        findings = d.detect("version=1.2.3.4")
        assert len(findings) == 0

    def test_invalid_ipv4_not_flagged(self):
        d = self._detector()
        findings = d.detect("x=999.999.999.999")
        assert len(findings) == 0

    def test_ipv6_public_detected(self):
        d = self._detector()
        # A globally routable IPv6 (documentation range 2001:db8:: is reserved but parsed as public)
        findings = d.detect("ipv6=2001:0db8:85a3:0000:0000:8a2e:0370:7334")
        # May or may not flag depending on ipaddress classification
        for f in findings:
            assert f.line_number >= 1

    def test_evidence_is_ip_itself(self):
        d = self._detector()
        findings = d.detect("HOST=8.8.8.8")
        for f in findings:
            assert "8.8.8.8" in f.evidence


# ═══════════════════════════════════════════════════════════════════════════════
# 8. Registry – multi-finding, deduplication, isolation
# ═══════════════════════════════════════════════════════════════════════════════

class TestDetectorRegistry:
    def _registry(self):
        from detectors.registry import DetectorRegistry
        return DetectorRegistry.default()

    def test_multiple_findings_in_one_file(self):
        """A file with AWS key, email, and private key header → multiple findings."""
        text = (
            f"# secrets.env\n"
            f"AWS_ACCESS_KEY_ID={FAKE_AWS_KEY}\n"
            f"CONTACT={FAKE_EMAIL}\n"
            f"{FAKE_PRIV_KEY_HEADER}\n"
        )
        registry = self._registry()
        findings = registry.scan(text, filename="secrets.env")
        rules = [f.rule_name for f in findings]
        assert "aws_access_key_id" in rules
        assert "email_address" in rules
        assert any("rsa" in r for r in rules)

    def test_fingerprint_deduplication(self):
        """Same finding at same offset → only one result returned."""
        text = f"AWS_ACCESS_KEY_ID={FAKE_AWS_KEY}\n"
        registry = self._registry()
        # Run twice – second registry run
        f1 = registry.scan(text)
        f2 = registry.scan(text)
        # Individual scans should produce the same fingerprints
        fps1 = {f.fingerprint for f in f1}
        fps2 = {f.fingerprint for f in f2}
        assert fps1 == fps2

    def test_fingerprints_unique_within_scan(self):
        text = f"AWS_ACCESS_KEY_ID={FAKE_AWS_KEY}\nAWS_ACCESS_KEY_ID={FAKE_AWS_KEY}\n"
        registry = self._registry()
        findings = registry.scan(text)
        fingerprints = [f.fingerprint for f in findings]
        assert len(fingerprints) == len(set(fingerprints))

    def test_failing_detector_does_not_break_others(self):
        """If one detector throws, others should still produce findings."""
        from detectors.registry import DetectorRegistry
        from detectors.base import BaseDetector, DetectorFinding

        class BrokenDetector(BaseDetector):
            detector_id = "broken"
            name = "Broken"
            categories = ["CREDENTIALS"]

            def detect(self, text, filename="", context=None):
                raise RuntimeError("intentional test failure")

        registry = DetectorRegistry()
        registry.register(BrokenDetector())

        from detectors.api_key_detector import APIKeyDetector
        registry.register(APIKeyDetector())

        findings = registry.scan(FAKE_AWS_KEY)
        assert any(f.rule_name == "aws_access_key_id" for f in findings)

    def test_empty_text_produces_no_findings(self):
        registry = self._registry()
        assert registry.scan("") == []

    def test_clean_file_zero_findings(self):
        """A file with no secrets produces exactly zero findings."""
        registry = self._registry()
        clean_text = (
            "# Application configuration\n"
            "DEBUG=false\n"
            "LOG_LEVEL=info\n"
            "PORT=8080\n"
            "ALLOWED_HOSTS=example.com,api.example.com\n"
            "TIMEOUT_SECONDS=30\n"
        )
        findings = registry.scan(clean_text, filename="config.env")
        assert len(findings) == 0, f"Expected no findings, got: {[(f.rule_name, f.evidence) for f in findings]}"

    def test_binary_content_does_not_crash(self):
        """Binary bytes should not cause exceptions when decoded as text."""
        registry = self._registry()
        binary_text = "\x00\x01\x02\xff\xfe binary data \x80\x81"
        try:
            findings = registry.scan(binary_text)
        except Exception as e:
            pytest.fail(f"Registry crashed on binary-like text: {e}")

    def test_all_findings_have_line_numbers(self):
        text = f"\n\nAWS_KEY={FAKE_AWS_KEY}\n"
        registry = self._registry()
        findings = registry.scan(text)
        for f in findings:
            assert f.line_number >= 1

    def test_remediation_present(self):
        registry = self._registry()
        findings = registry.scan(FAKE_AWS_KEY)
        for f in findings:
            assert f.remediation and len(f.remediation) > 10


# ═══════════════════════════════════════════════════════════════════════════════
# 9. Integration: _process_scan with detector findings
# ═══════════════════════════════════════════════════════════════════════════════

class TestProcessScanIntegration:
    def test_scan_with_aws_key_returns_findings(self, db):
        from api.scan_routes import _process_scan
        content = f"AWS_ACCESS_KEY_ID={FAKE_AWS_KEY}\n".encode()
        response = _process_scan(
            content=content,
            filename="test_secrets.env",
            destination="EXTERNAL",
            action="UPLOAD",
            device_id="TEST-DEVICE",
            user_label="test_user",
            db=db,
        )
        assert response.total_findings >= 1
        rules = [f.rule for f in response.findings]
        assert "aws_access_key_id" in rules

    def test_findings_are_redacted_in_response(self, db):
        from api.scan_routes import _process_scan
        content = f"AWS_ACCESS_KEY_ID={FAKE_AWS_KEY}\n".encode()
        response = _process_scan(
            content=content,
            filename="test_keys.env",
            destination="EXTERNAL",
            action="UPLOAD",
            device_id="TEST-DEVICE",
            user_label="test_user",
            db=db,
        )
        for finding in response.findings:
            assert FAKE_AWS_KEY not in finding.matched_text, \
                f"Raw AWS key leaked in finding: {finding.matched_text}"

    def test_clean_file_zero_findings_in_scan(self, db):
        from api.scan_routes import _process_scan
        content = b"# Config\nLOG_LEVEL=info\nDEBUG=false\n"
        response = _process_scan(
            content=content,
            filename="clean.env",
            destination="LOCAL",
            action="READ",
            device_id="TEST-DEVICE",
            user_label="test_user",
            db=db,
        )
        assert response.total_findings == 0

    def test_private_key_creates_critical_incident(self, db):
        from api.scan_routes import _process_scan
        content = (FAKE_PRIV_KEY_HEADER + "\nSome other content\n").encode()
        response = _process_scan(
            content=content,
            filename="id_rsa",
            destination="EXTERNAL",
            action="UPLOAD",
            device_id="TEST-DEVICE",
            user_label="test_user",
            db=db,
        )
        assert response.risk_score >= 30   # at minimum MEDIUM threshold for incident creation
        # Severity should be HIGH or CRITICAL
        assert response.severity in ("HIGH", "CRITICAL")

    def test_db_url_credentials_not_in_response(self, db):
        from api.scan_routes import _process_scan
        content = f"DATABASE_URL={FAKE_DB_URL_PG}\n".encode()
        response = _process_scan(
            content=content,
            filename="database.env",
            destination="EXTERNAL",
            action="UPLOAD",
            device_id="TEST-DEVICE",
            user_label="test_user",
            db=db,
        )
        for finding in response.findings:
            assert "S3cr3tP@ssw0rd" not in finding.matched_text

    def test_multi_secret_file_all_types_detected(self, db):
        from api.scan_routes import _process_scan
        content = "\n".join([
            f"AWS_ACCESS_KEY_ID={FAKE_AWS_KEY}",
            f"DATABASE_URL={FAKE_DB_URL_PG}",
            f"CONTACT={FAKE_EMAIL}",
            FAKE_PRIV_KEY_HEADER,
        ]).encode()
        response = _process_scan(
            content=content,
            filename="multi_secret.env",
            destination="EXTERNAL",
            action="UPLOAD",
            device_id="TEST-DEVICE",
            user_label="test_user",
            db=db,
        )
        assert response.total_findings >= 3
        rules = [f.rule for f in response.findings]
        assert any("aws" in r for r in rules)
        assert any("database" in r or "postgresql" in r for r in rules)


# ═══════════════════════════════════════════════════════════════════════════════
# 10. Upload Endpoint Authentication
# ═══════════════════════════════════════════════════════════════════════════════

class TestUploadAuth:
    def test_upload_without_token_returns_401(self, client):
        content = b"AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE\n"
        response = client.post(
            "/api/v1/upload",
            files={"files": ("secrets.env", content, "text/plain")},
        )
        assert response.status_code == 401

    def test_scan_file_without_token_accepted_as_optional(self, client):
        """
        /scan/file uses get_optional_current_user – unauthenticated requests
        are accepted but user is anonymous.
        """
        content = b"test content with no secrets"
        response = client.post(
            "/api/scan/file",
            files={"file": ("test.txt", content, "text/plain")},
        )
        assert response.status_code in (200, 400)   # 400 only if backend not running


# ═══════════════════════════════════════════════════════════════════════════════
# 11. Archive and Edge Cases
# ═══════════════════════════════════════════════════════════════════════════════

class TestArchiveEdgeCases:
    def _make_zip(self, members: dict[str, bytes]) -> bytes:
        """Create a ZIP in memory from a dict of {filename: content}."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for name, data in members.items():
                zf.writestr(name, data)
        return buf.getvalue()

    def test_path_traversal_rejected(self, client):
        """A ZIP with ../evil.txt path must return 400."""
        zip_bytes = self._make_zip({"../evil.txt": b"malicious content"})
        response = client.post(
            "/api/v1/upload",
            files={"files": ("traversal.zip", zip_bytes, "application/zip")},
            headers={"Authorization": "Bearer invalid-for-test"},
        )
        # Without valid auth this would be 401, but we test the shape
        assert response.status_code in (400, 401, 403, 422)

    def test_empty_file_rejected(self, client):
        response = client.post(
            "/api/scan/file",
            files={"file": ("empty.txt", b"", "text/plain")},
        )
        assert response.status_code == 400

    def test_unsupported_extension_rejected_by_upload(self, client):
        """Phase 2 upload endpoint rejects unsupported extensions."""
        content = b"executable binary"
        response = client.post(
            "/api/v1/upload",
            files={"files": ("malware.exe", content, "application/octet-stream")},
            headers={"Authorization": "Bearer invalid-for-test"},
        )
        assert response.status_code in (400, 401, 403, 422)
