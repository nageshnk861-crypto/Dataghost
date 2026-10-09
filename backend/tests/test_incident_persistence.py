"""
Tests for DataGhost Incident Database & Persistence Layer (Phase 4).
Validates Incident ORM models, lifecycle status transitions, pagination, filtering,
and strict non-plaintext secret persistence protections.
All test credentials and PII samples are fake mock values.
"""
import json
import re
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from main import app
from database import SessionLocal, init_db
from models import Incident

client = TestClient(app)

INCIDENT_ID_PATTERN = re.compile(r"^DG-\d{4}-\d{4,}$")


@pytest.fixture(autouse=True)
def ensure_db():
    init_db()


# ---------------------------------------------------------------------------
# 1. Incident Creation and ID Format Tests
# ---------------------------------------------------------------------------

class TestIncidentCreationAndFormat:
    def test_incident_created_after_high_risk_scan(self):
        """Scanning restricted/critical text triggers an Incident with DG-YYYY-XXXX ID format."""
        payload = {
            "text": "CRITICAL: aws_access_key_id = AKIAIOSFODNN7EXAMPLE for user audit",
            "filename": "server_creds.env",
            "classification": "RESTRICTED",
            "destination": "CLOUD",
            "action": "UPLOAD",
        }
        res = client.post("/scan", json=payload)
        assert res.status_code == 200
        data = res.json()

        assert data["risk_score"] >= 30
        assert data["incident_id"] is not None
        assert INCIDENT_ID_PATTERN.match(data["incident_id"])

        # Fetch from database to verify persistence
        db = SessionLocal()
        try:
            inc = db.query(Incident).filter(Incident.incident_id == data["incident_id"]).first()
            assert inc is not None
            assert inc.filename == "server_creds.env"
            assert inc.status == "OPEN"
            assert inc.classification == "RESTRICTED"
            assert inc.destination == "CLOUD"
            assert inc.severity in ("HIGH", "CRITICAL")
        finally:
            db.close()

    def test_incident_persists_across_sessions(self):
        """Incident record remains fully readable in a completely new database session."""
        inc_id = f"DG-{datetime.now(timezone.utc).year}-9999"
        
        # Session 1: Create
        db1 = SessionLocal()
        try:
            # Clean up if existed from previous run
            db1.query(Incident).filter(Incident.incident_id == inc_id).delete()
            db1.commit()

            new_inc = Incident(
                incident_id=inc_id,
                filename="isolated_test.txt",
                classification="CONFIDENTIAL",
                risk_score=75,
                severity="HIGH",
                recommended_action="ALERT",
                action_taken="ALERTED",
                destination="EXTERNAL",
                action="UPLOAD",
                status="OPEN",
                findings_json=json.dumps([{"rule": "pan_card", "matched_text": "AB******4F", "category": "PII"}]),
            )
            db1.add(new_inc)
            db1.commit()
        finally:
            db1.close()

        # Session 2: Read in new session
        db2 = SessionLocal()
        try:
            fetched = db2.query(Incident).filter(Incident.incident_id == inc_id).first()
            assert fetched is not None
            assert fetched.filename == "isolated_test.txt"
            assert fetched.status == "OPEN"
            assert fetched.risk_score == 75

            # Cleanup
            db2.delete(fetched)
            db2.commit()
        finally:
            db2.close()


# ---------------------------------------------------------------------------
# 2. Incident Status Workflow Tests (OPEN -> ACKNOWLEDGED -> RESOLVED)
# ---------------------------------------------------------------------------

class TestIncidentStatusWorkflow:
    @pytest.fixture
    def sample_incident(self):
        inc_id = f"DG-{datetime.now(timezone.utc).year}-7777"
        db = SessionLocal()
        try:
            db.query(Incident).filter(Incident.incident_id == inc_id).delete()
            db.commit()

            inc = Incident(
                incident_id=inc_id,
                filename="workflow_test.txt",
                classification="CONFIDENTIAL",
                risk_score=65,
                severity="HIGH",
                recommended_action="ALERT",
                action_taken="ALERTED",
                destination="CLOUD",
                action="SHARE",
                status="OPEN",
            )
            db.add(inc)
            db.commit()
            db.refresh(inc)
            yield inc_id
            
            # Teardown
            db.query(Incident).filter(Incident.incident_id == inc_id).delete()
            db.commit()
        finally:
            db.close()

    def test_default_status_is_open(self, sample_incident):
        res = client.get(f"/incidents/{sample_incident}")
        assert res.status_code == 200
        assert res.json()["status"] == "OPEN"

    def test_transition_to_acknowledged(self, sample_incident):
        res = client.patch(f"/incidents/{sample_incident}", json={"status": "ACKNOWLEDGED"})
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ACKNOWLEDGED"

        # Verify DB persisted
        db = SessionLocal()
        try:
            inc = db.query(Incident).filter(Incident.incident_id == sample_incident).first()
            assert inc.status == "ACKNOWLEDGED"
        finally:
            db.close()

    def test_transition_to_resolved(self, sample_incident):
        res = client.patch(f"/incidents/{sample_incident}", json={"status": "RESOLVED"})
        assert res.status_code == 200
        assert res.json()["status"] == "RESOLVED"

    def test_invalid_status_rejected(self, sample_incident):
        res = client.patch(f"/incidents/{sample_incident}", json={"status": "INVALID_STATUS_CODE"})
        assert res.status_code == 400
        assert "invalid status" in res.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 3. Incident List, Filtering, and Pagination Tests
# ---------------------------------------------------------------------------

class TestIncidentListAndFiltering:
    @pytest.fixture(scope="class", autouse=True)
    def seed_test_incidents(self):
        db = SessionLocal()
        created_ids = []
        try:
            year = datetime.now(timezone.utc).year
            test_specs = [
                ("DG-TEST-0001", "CRITICAL", "OPEN", "RESTRICTED", "EXTERNAL", "BLOCK"),
                ("DG-TEST-0002", "HIGH", "ACKNOWLEDGED", "CONFIDENTIAL", "CLOUD", "ALERT"),
                ("DG-TEST-0003", "MEDIUM", "RESOLVED", "INTERNAL", "INTERNAL", "ALERT"),
                ("DG-TEST-0004", "LOW", "OPEN", "PUBLIC", "LOCAL", "ALLOW"),
                ("DG-TEST-0005", "CRITICAL", "OPEN", "RESTRICTED", "USB", "BLOCK"),
            ]
            for inc_id, sev, st, cls, dest, rec in test_specs:
                db.query(Incident).filter(Incident.incident_id == inc_id).delete()
                inc = Incident(
                    incident_id=inc_id,
                    filename=f"{inc_id.lower()}.txt",
                    classification=cls,
                    risk_score=90 if sev == "CRITICAL" else (70 if sev == "HIGH" else 40),
                    severity=sev,
                    recommended_action=rec,
                    action_taken="BLOCKED" if sev == "CRITICAL" else "ALERTED",
                    destination=dest,
                    action="UPLOAD",
                    status=st,
                )
                db.add(inc)
                created_ids.append(inc_id)
            db.commit()
            yield
            for inc_id in created_ids:
                db.query(Incident).filter(Incident.incident_id == inc_id).delete()
            db.commit()
        finally:
            db.close()

    def test_incident_list_pagination(self):
        res = client.get("/incidents?page=1&page_size=3")
        assert res.status_code == 200
        data = res.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert data["page"] == 1
        assert len(data["items"]) <= 3

    def test_filter_by_severity(self):
        res = client.get("/incidents?severity=CRITICAL")
        assert res.status_code == 200
        items = res.json()["items"]
        assert len(items) >= 2
        for item in items:
            assert item["severity"] == "CRITICAL"

    def test_filter_by_status(self):
        res = client.get("/incidents?status=ACKNOWLEDGED")
        assert res.status_code == 200
        items = res.json()["items"]
        assert len(items) >= 1
        for item in items:
            assert item["status"] == "ACKNOWLEDGED"

    def test_filter_by_classification(self):
        res = client.get("/incidents?classification=RESTRICTED")
        assert res.status_code == 200
        items = res.json()["items"]
        assert len(items) >= 2
        for item in items:
            assert item["classification"] == "RESTRICTED"

    def test_filter_by_destination(self):
        res = client.get("/incidents?destination=USB")
        assert res.status_code == 200
        items = res.json()["items"]
        for item in items:
            assert item["destination"] == "USB"


# ---------------------------------------------------------------------------
# 4. Secret Storage Protection Tests (NO PLAINTEXT SECRETS IN DATABASE)
# ---------------------------------------------------------------------------

class TestSecretStorageProtection:
    def test_no_raw_secrets_stored_in_database(self):
        """Ensure passwords, API keys, JWTs, PAN, Aadhaar, and credit cards are NEVER saved as plaintext."""
        fake_api_key = "abcdef1234567890abcdef1234567890"
        fake_aws_key = "AKIAIOSFODNN7EXAMPLE"
        fake_jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        fake_pan = "ABCDE1234F"
        fake_aadhaar = "2345 6789 0123"
        fake_cc = "4111111111111111"
        fake_pwd = "SuperSecretPassword123!"

        payload = {
            "text": f"""
            Database credentials backup:
            api_key = {fake_api_key}
            aws_key = {fake_aws_key}
            token = {fake_jwt}
            PAN = {fake_pan}
            Aadhaar = {fake_aadhaar}
            card = {fake_cc}
            password = {fake_pwd}
            """,
            "filename": "security_test.txt",
            "classification": "RESTRICTED",
            "destination": "EXTERNAL",
            "action": "UPLOAD",
        }

        res = client.post("/scan", json=payload)
        assert res.status_code == 200
        incident_id = res.json()["incident_id"]
        assert incident_id is not None

        # Direct database row inspection
        db = SessionLocal()
        try:
            inc = db.query(Incident).filter(Incident.incident_id == incident_id).first()
            assert inc is not None

            # Retrieve raw findings_json string stored in DB
            stored_json = inc.findings_json
            assert stored_json is not None

            # 1. Plaintext API key must NOT be anywhere in stored DB record
            assert fake_api_key not in stored_json

            # 2. Plaintext AWS key must NOT be in stored DB record
            assert fake_aws_key not in stored_json

            # 3. Plaintext JWT must NOT be in stored DB record
            assert fake_jwt not in stored_json

            # 4. Plaintext PAN must NOT be in stored DB record
            assert fake_pan not in stored_json

            # 5. Plaintext Aadhaar must NOT be in stored DB record
            assert fake_aadhaar not in stored_json

            # 6. Plaintext Credit Card must NOT be in stored DB record
            assert fake_cc not in stored_json

            # 7. Plaintext Password must NOT be in stored DB record
            assert fake_pwd not in stored_json

            # 8. Stored JSON must contain masked asterisks
            assert "*" in stored_json

            # Cleanup
            db.delete(inc)
            db.commit()
        finally:
            db.close()
