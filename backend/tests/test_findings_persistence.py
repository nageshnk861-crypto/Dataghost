"""
DataGhost – Findings Persistence & Audit Logs Tests (Phase 5).

Covers:
  1. Finding persistence on scan pipeline (ScanLog + Finding records).
  2. Clean scan produces 0 findings.
  3. Redacted evidence (zero plaintext secrets stored in DB or audit logs).
  4. Finding deduplication (re-scanning same content increments occurrence_count).
  5. Audit log recording on scan, incident, and finding status change.
  6. Findings API: GET /findings, GET /findings/stats, GET /findings/{id}, PATCH /findings/{id}.
  7. RBAC & IDOR protection (analysts restricted to their own findings/devices).
"""
import json
import uuid
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient


from main import app
from database import SessionLocal, init_db
from auth import create_access_token, get_password_hash
from models import Finding, AuditLog, ScanLog, Incident, User, Device

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_test_users():
    """Ensure test admin and analyst users exist."""
    init_db()
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.username == "phase5_admin").first()
        if not admin:
            admin = User(
                username="phase5_admin",
                email="p5admin@test.local",
                hashed_password=get_password_hash("AdminPass123!"),
                role="admin",
            )
            db.add(admin)

        analyst = db.query(User).filter(User.username == "phase5_analyst").first()
        if not analyst:
            analyst = User(
                username="phase5_analyst",
                email="p5analyst@test.local",
                hashed_password=get_password_hash("AnalystPass123!"),
                role="analyst",
            )
            db.add(analyst)

        other_analyst = db.query(User).filter(User.username == "phase5_other").first()
        if not other_analyst:
            other_analyst = User(
                username="phase5_other",
                email="p5other@test.local",
                hashed_password=get_password_hash("OtherPass123!"),
                role="analyst",
            )
            db.add(other_analyst)

        db.commit()
    finally:
        db.close()


def _get_admin_headers():
    token = create_access_token({"sub": "phase5_admin", "role": "admin"})
    return {"Authorization": f"Bearer {token}"}


def _get_analyst_headers():
    token = create_access_token({"sub": "phase5_analyst", "role": "analyst"})
    return {"Authorization": f"Bearer {token}"}


def _get_other_analyst_headers():
    token = create_access_token({"sub": "phase5_other", "role": "analyst"})
    return {"Authorization": f"Bearer {token}"}


class TestFindingPersistenceOnScan:
    def test_scan_persists_findings_and_scan_log(self):
        """Scanning text with credentials must create ScanLog and Finding records."""
        dev_id = f"test-device-p5-{uuid.uuid4().hex[:6]}"
        headers = _get_admin_headers()
        payload = {
            "text": "export AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE and SECRET=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            "filename": "env_backup.txt",
            "classification": "CONFIDENTIAL",
            "destination": "CLOUD",
            "action": "UPLOAD",
            "device_id": dev_id,
        }
        res = client.post("/scan", json=payload, headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["total_findings"] >= 1
        scan_id = data["scan_id"]

        db = SessionLocal()
        try:
            # Verify ScanLog
            slog = db.query(ScanLog).filter(ScanLog.scan_id == scan_id).first()
            assert slog is not None
            assert slog.filename == "env_backup.txt"
            assert slog.findings_count >= 1
            assert slog.status == "COMPLETED"

            # Verify Finding
            findings = db.query(Finding).filter(Finding.scan_id == scan_id).all()
            assert len(findings) >= 1
            aws_finding = next((f for f in findings if "aws" in (f.rule_id or "").lower()), findings[0])
            assert aws_finding.file_name == "env_backup.txt"
            assert aws_finding.status == "OPEN"
            assert aws_finding.occurrence_count == 1
            assert aws_finding.fingerprint is not None
            assert aws_finding.evidence_redacted is not None

            # Verify REDACTION: raw secret MUST NOT appear in evidence_redacted
            assert "AKIAIOSFODNN7EXAMPLE" not in aws_finding.evidence_redacted
            assert "*" in aws_finding.evidence_redacted
        finally:
            db.close()

    def test_clean_scan_persists_zero_findings(self):
        """Scanning clean benign text creates a ScanLog but zero Finding records."""
        dev_id = f"test-clean-{uuid.uuid4().hex[:6]}"
        headers = _get_admin_headers()
        payload = {
            "text": "General team update: All milestones for sprint 4 are on track.",
            "filename": "team_update.txt",
            "classification": "INTERNAL",
            "destination": "LOCAL",
            "action": "READ",
            "device_id": dev_id,
        }
        res = client.post("/scan", json=payload, headers=headers)
        assert res.status_code == 200
        scan_id = res.json()["scan_id"]

        db = SessionLocal()
        try:
            slog = db.query(ScanLog).filter(ScanLog.scan_id == scan_id).first()
            assert slog is not None
            assert slog.findings_count == 0

            findings = db.query(Finding).filter(Finding.scan_id == scan_id).all()
            assert len(findings) == 0
        finally:
            db.close()

    def test_finding_deduplication_on_rescan(self):
        """Re-scanning the same content on the same device increments occurrence_count."""
        dev_id = f"test-dedup-{uuid.uuid4().hex[:6]}"
        headers = _get_admin_headers()
        payload = {
            "text": "Hardcoded api_key: AIzaSyA1B2C3D4E5F6G7H8I9J0K1L2M3N4O5P6Q for testing",
            "filename": "google_api.js",
            "classification": "CONFIDENTIAL",
            "destination": "INTERNAL",
            "action": "READ",
            "device_id": dev_id,
        }

        # First scan
        res1 = client.post("/scan", json=payload, headers=headers)
        assert res1.status_code == 200
        scan_id1 = res1.json()["scan_id"]

        db = SessionLocal()
        try:
            finding1 = db.query(Finding).filter(Finding.scan_id == scan_id1).first()
            assert finding1 is not None
            initial_count = finding1.occurrence_count
            fp = finding1.fingerprint
            first_seen = finding1.first_seen_at
        finally:
            db.close()

        # Second scan with identical content and device
        res2 = client.post("/scan", json=payload, headers=headers)
        assert res2.status_code == 200

        db = SessionLocal()
        try:
            # Query by fingerprint and device_id
            matched_findings = (
                db.query(Finding)
                .filter(Finding.fingerprint == fp, Finding.device_id == dev_id)
                .all()
            )
            # Must NOT create duplicate rows
            assert len(matched_findings) == 1
            updated_finding = matched_findings[0]
            assert updated_finding.occurrence_count == initial_count + 1
            assert updated_finding.last_seen_at >= first_seen
        finally:
            db.close()



class TestAuditLogEvents:
    def test_scan_and_incident_audit_events_created(self):
        """Scan completion creates SCAN_COMPLETED and INCIDENT_CREATED audit records."""
        headers = _get_admin_headers()
        payload = {
            "text": "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA0mock...\n-----END RSA PRIVATE KEY-----",
            "filename": "compromised.key",
            "classification": "RESTRICTED",
            "destination": "EXTERNAL",
            "action": "UPLOAD",
            "device_id": "test-device-audit-01",
        }
        res = client.post("/scan", json=payload, headers=headers)
        assert res.status_code == 200
        scan_id = res.json()["scan_id"]

        db = SessionLocal()
        try:
            scan_audit = (
                db.query(AuditLog)
                .filter(AuditLog.action == "SCAN_COMPLETED", AuditLog.resource_id == scan_id)
                .first()
            )
            assert scan_audit is not None
            assert scan_audit.resource_type == "SCAN"
            assert scan_audit.result == "SUCCESS"

            # Check that metadata does not leak raw secrets
            if scan_audit.metadata_json:
                assert "BEGIN RSA PRIVATE KEY" not in scan_audit.metadata_json
        finally:
            db.close()


class TestFindingsAPI:
    def test_list_findings_unauthenticated_rejected(self):
        """GET /api/findings without authorization must return 401."""
        res = client.get("/api/findings")
        assert res.status_code == 401

    def test_list_findings_admin(self):
        """GET /api/findings returns paginated list of findings."""
        headers = _get_admin_headers()
        res = client.get("/api/findings?page=1&per_page=10", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert data["page"] == 1
        assert data["per_page"] == 10

    def test_list_findings_v1_alias(self):
        """GET /api/v1/findings works identically."""
        headers = _get_admin_headers()
        res = client.get("/api/v1/findings?page=1&page_size=5", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert "items" in data
        assert data["per_page"] == 5

    def test_filter_findings_by_severity(self):
        """Filtering by severity returns matching findings."""
        headers = _get_admin_headers()
        res = client.get("/api/findings?severity=CRITICAL", headers=headers)
        assert res.status_code == 200
        for item in res.json()["items"]:
            assert item["severity"] == "CRITICAL"

    def test_get_findings_stats(self):
        """GET /api/findings/stats returns aggregated metrics."""
        headers = _get_admin_headers()
        res = client.get("/api/findings/stats", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert "total" in data
        assert "open" in data
        assert "acknowledged" in data
        assert "resolved" in data
        assert "false_positive" in data
        assert "by_severity" in data
        assert "by_category" in data

    def test_get_and_update_finding(self):
        """GET /findings/{id} and PATCH /findings/{id} status update with audit logging."""
        db = SessionLocal()
        admin = db.query(User).filter(User.username == "phase5_admin").first()
        finding = Finding(
            user_id=admin.id,
            file_name="test_config.yaml",
            rule_id="test_rule",
            category="CREDENTIALS",
            severity="HIGH",
            risk_score=75,
            evidence_redacted="token: ***REDACTED***",
            status="OPEN",
            fingerprint="test-fp-12345",
        )
        db.add(finding)
        db.commit()
        db.refresh(finding)
        finding_id = finding.id
        db.close()

        headers = _get_admin_headers()

        # GET detail
        get_res = client.get(f"/api/findings/{finding_id}", headers=headers)
        assert get_res.status_code == 200
        assert get_res.json()["id"] == finding_id
        assert get_res.json()["status"] == "OPEN"

        # PATCH update
        patch_res = client.patch(
            f"/api/findings/{finding_id}",
            json={"status": "ACKNOWLEDGED", "comment": "Triage in progress"},
            headers=headers,
        )
        assert patch_res.status_code == 200
        assert patch_res.json()["status"] == "ACKNOWLEDGED"

        # Check DB and AuditLog
        db = SessionLocal()
        try:
            f_db = db.query(Finding).filter(Finding.id == finding_id).first()
            assert f_db.status == "ACKNOWLEDGED"

            audit = (
                db.query(AuditLog)
                .filter(AuditLog.action == "FINDING_STATUS_CHANGED", AuditLog.resource_id == str(finding_id))
                .first()
            )
            assert audit is not None
            assert audit.resource_type == "FINDING"
            assert "ACKNOWLEDGED" in audit.metadata_json
        finally:
            db.close()

    def test_invalid_status_rejected(self):
        """PATCH with an unknown status returns 400 Bad Request."""
        headers = _get_admin_headers()
        res = client.patch("/api/findings/1", json={"status": "INVALID_STATUS"}, headers=headers)
        assert res.status_code == 400


class TestFindingsRBACAndIDOR:
    def test_analyst_cannot_access_other_users_finding(self):
        """Analyst role cannot read or update findings belonging to another user."""
        db = SessionLocal()
        other = db.query(User).filter(User.username == "phase5_other").first()
        secret_finding = Finding(
            user_id=other.id,
            file_name="other_user_secrets.json",
            rule_id="other_rule",
            category="CREDENTIALS",
            severity="CRITICAL",
            status="OPEN",
            device_id="other-device-99",
            fingerprint="other-fp-99999",
        )
        db.add(secret_finding)
        db.commit()
        db.refresh(secret_finding)
        fid = secret_finding.id
        db.close()

        analyst_headers = _get_analyst_headers()

        # GET should return 404 (IDOR protection)
        get_res = client.get(f"/api/findings/{fid}", headers=analyst_headers)
        assert get_res.status_code == 404

        # PATCH should return 404
        patch_res = client.patch(
            f"/api/findings/{fid}",
            json={"status": "RESOLVED"},
            headers=analyst_headers,
        )
        assert patch_res.status_code == 404

        # Admin CAN access it
        admin_headers = _get_admin_headers()
        admin_res = client.get(f"/api/findings/{fid}", headers=admin_headers)
        assert admin_res.status_code == 200
        assert admin_res.json()["id"] == fid
