"""
Tests for DataGhost FastAPI Application (Phase 3).
Validates /health, /scan, /scan/file, sensitive text masking, error responses,
and OpenAPI / Swagger doc availability.
All test samples use mock/fake data.
"""
import io
import pytest
from fastapi.testclient import TestClient

from main import app
from schemas.schemas import ScanResponse, HealthResponse

client = TestClient(app)


# ---------------------------------------------------------------------------
# 1. Health Endpoint Tests
# ---------------------------------------------------------------------------

def test_health_check():
    """Verify GET /health returns 200 OK with expected status and version."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["version"] == "1.0.0"


# ---------------------------------------------------------------------------
# 2. Text Scanning (POST /scan and POST /api/scan) Tests
# ---------------------------------------------------------------------------

class TestTextScanAPI:
    def test_clean_text_scan(self):
        """Benign public text scan should return LOW risk with ALLOW action."""
        payload = {
            "text": "The quarterly project status meeting is scheduled for Monday at 10 AM.",
            "filename": "meeting_notes.txt",
            "classification": "PUBLIC",
            "destination": "LOCAL",
            "action": "READ",
            "file_size": 1000,
        }
        response = client.post("/scan", json=payload)
        assert response.status_code == 200
        data = response.json()

        assert "scan_id" in data
        assert data["filename"] == "meeting_notes.txt"
        assert data["total_findings"] == 0
        assert data["findings"] == []
        assert data["classification"] == "PUBLIC"
        assert data["risk_score"] < 30
        assert data["severity"] == "LOW"
        assert data["recommended_action"] == "ALLOW"
        assert data["action_taken"] == "ALLOWED"

    def test_sensitive_text_scan_and_masking(self):
        """Text containing PII & credentials should return masked findings and elevated risk."""
        payload = {
            "text": "Alert: AWS key AKIAIOSFODNN7EXAMPLE and PAN ABCDE1234F found for rahul.sharma@example.com",
            "filename": "credentials_dump.txt",
            "classification": "CONFIDENTIAL",
            "destination": "CLOUD",
            "action": "SHARE",
            "file_size": 5000,
        }
        response = client.post("/scan", json=payload)
        assert response.status_code == 200
        data = response.json()

        assert data["total_findings"] >= 3
        rules_found = [f["rule"] for f in data["findings"]]
        assert "aws_access_key" in rules_found
        assert "pan_card" in rules_found
        assert "email_address" in rules_found

        # Sensitive Data Masking Verification:
        # Verify raw credentials/secrets are NOT returned directly in cleartext
        aws_finding = next(f for f in data["findings"] if f["rule"] == "aws_access_key")
        assert aws_finding["matched_text"] != "AKIAIOSFODNN7EXAMPLE"
        assert "*" in aws_finding["matched_text"]
        assert aws_finding["matched_text"].startswith("AKIA")

        pan_finding = next(f for f in data["findings"] if f["rule"] == "pan_card")
        assert pan_finding["matched_text"] != "ABCDE1234F"
        assert "*" in pan_finding["matched_text"]

        email_finding = next(f for f in data["findings"] if f["rule"] == "email_address")
        assert email_finding["matched_text"] != "rahul.sharma@example.com"
        assert "*" in email_finding["matched_text"]

        # Risk score and action verification
        assert data["risk_score"] >= 60
        assert data["severity"] in ("HIGH", "CRITICAL")
        assert data["recommended_action"] in ("ALERT", "BLOCK")

    def test_critical_restricted_exfiltration_blocked(self):
        """Restricted data with credentials uploaded externally must trigger BLOCK."""
        payload = {
            "text": "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA0mock...\n-----END RSA PRIVATE KEY-----",
            "filename": "server.key",
            "classification": "RESTRICTED",
            "destination": "EXTERNAL",
            "action": "UPLOAD",
            "file_size": 600000,
        }
        response = client.post("/scan", json=payload)
        assert response.status_code == 200
        data = response.json()

        assert data["risk_score"] >= 80
        assert data["severity"] == "CRITICAL"
        assert data["recommended_action"] == "BLOCK"
        assert data["action_taken"] == "BLOCKED"

    def test_alias_scan_text_endpoint(self):
        """Verify POST /scan/text alias works identically."""
        payload = {
            "text": "General notice without sensitive content.",
            "filename": "notice.txt",
        }
        response = client.post("/scan/text", json=payload)
        assert response.status_code == 200
        assert response.json()["total_findings"] == 0

    def test_missing_text_payload_validation(self):
        """Missing required 'text' field should return 422 Unprocessable Entity."""
        response = client.post("/scan", json={"filename": "bad_request.txt"})
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# 3. File Upload Scanning (POST /scan/file) Tests
# ---------------------------------------------------------------------------

class TestFileScanAPI:
    def test_upload_valid_file(self):
        """Uploading a text file containing sensitive data should scan and return findings."""
        file_content = b"CONFIDENTIAL\nEmployee ID: EMP-9021\nContact: employee@company.local\nBank account: 123456789012"
        files = {"file": ("report.txt", io.BytesIO(file_content), "text/plain")}
        data = {
            "classification": "CONFIDENTIAL",
            "destination": "INTERNAL",
            "action": "COPY",
        }
        response = client.post("/scan/file", files=files, data=data)
        assert response.status_code == 200
        res = response.json()

        assert res["filename"] == "report.txt"
        assert res["total_findings"] >= 2
        assert "scan_id" in res
        assert res["risk_score"] > 0
        assert res["severity"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")

    def test_upload_empty_file_error(self):
        """Uploading an empty file should return 400 Bad Request with useful message."""
        files = {"file": ("empty.txt", io.BytesIO(b""), "text/plain")}
        response = client.post("/scan/file", files=files)
        assert response.status_code == 400
        assert "empty" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 4. OpenAPI & Swagger Documentation
# ---------------------------------------------------------------------------

def test_openapi_and_docs_available():
    """Verify OpenAPI JSON schema and Swagger UI are accessible."""
    docs_res = client.get("/docs")
    assert docs_res.status_code == 200
    assert "swagger" in docs_res.text.lower() or "html" in docs_res.text.lower()

    openapi_res = client.get("/openapi.json")
    assert openapi_res.status_code == 200
    schema = openapi_res.json()
    assert "/health" in schema["paths"]
    assert "/scan" in schema["paths"]
    assert "/scan/file" in schema["paths"]
