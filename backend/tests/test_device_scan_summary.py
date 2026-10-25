"""
DataGhost – Endpoint Scan Summary Audit Tests.

Proves:
  1. If no agent or scan data exists for a device, returns "No scan data yet" with risk_score: None (never a score).
  2. A failed scan returns an error (never "allowed" or "scan complete").
  3. Real detector scan persists Finding records with redacted evidence.
  4. Endpoint Scan Summary metrics (risk score, sensitive files, findings, blocked transfers,
     user_information_count, ai_model_sharing_count) are computed strictly from persisted DB findings.
  5. Simulation is strictly gated behind an explicit DEMO flag and returns is_simulated: True.
"""
import os
import uuid
import pytest
from fastapi.testclient import TestClient

from main import app
from database import SessionLocal, init_db
from auth import create_access_token, get_password_hash
from models import Device, Finding, Incident, ScanLog, User

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_test_users():
    """Ensure test admin and analyst users exist."""
    init_db()
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.username == "summary_admin").first()
        if not admin:
            admin = User(
                username="summary_admin",
                email="summary_admin@test.local",
                hashed_password=get_password_hash("AdminPass123!"),
                role="admin",
            )
            db.add(admin)

        analyst = db.query(User).filter(User.username == "summary_analyst").first()
        if not analyst:
            analyst = User(
                username="summary_analyst",
                email="summary_analyst@test.local",
                hashed_password=get_password_hash("AnalystPass123!"),
                role="analyst",
            )
            db.add(analyst)

        db.commit()
    finally:
        db.close()


def _get_admin_headers():
    token = create_access_token({"sub": "summary_admin", "role": "admin"})
    return {"Authorization": f"Bearer {token}"}


def _get_analyst_headers():
    token = create_access_token({"sub": "summary_analyst", "role": "analyst"})
    return {"Authorization": f"Bearer {token}"}


def _create_test_device(device_id: str, device_name: str = "Test Endpoint"):
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.username == "summary_admin").first()
        dev = Device(
            device_id=device_id,
            device_name=device_name,
            platform="Windows",
            status="ACTIVE",
            user_id=admin.id if admin else None,
            files_scanned=0,
            incidents_count=0,
        )
        db.add(dev)
        db.commit()
        db.refresh(dev)
        return dev
    finally:
        db.close()


def _create_analyst_device(device_id: str, device_name: str = "Analyst Device"):
    db = SessionLocal()
    try:
        analyst = db.query(User).filter(User.username == "summary_analyst").first()
        dev = Device(
            device_id=device_id,
            device_name=device_name,
            platform="Windows",
            status="ACTIVE",
            user_id=analyst.id if analyst else None,
            files_scanned=0,
            incidents_count=0,
        )
        db.add(dev)
        db.commit()
        db.refresh(dev)
        return dev
    finally:
        db.close()


class TestEndpointScanSummary:
    def test_no_scan_data_yet_never_returns_score(self):
        """If no scan data exists for a device, show 'No scan data yet', never a score."""
        dev_id = f"test-empty-{uuid.uuid4().hex[:6]}"
        _create_test_device(dev_id, "Clean Laptop")
        headers = _get_admin_headers()

        # GET scan-summary
        res = client.get(f"/api/devices/{dev_id}/scan-summary", headers=headers)
        assert res.status_code == 200
        data = res.json()

        assert data["has_scan_data"] is False
        assert data["message"] == "No scan data yet"
        assert data["risk_score"] is None, "A device with no scan data must never have a risk score"
        assert data["risk_level"] is None
        assert data["block_level"] is None
        assert data["sensitive_files"] == 0
        assert data["threats_detected"] == 0
        assert data["scan_results"] == []

    def test_summary_equals_persisted_findings_from_real_detector(self):
        """
        Summary must be computed ONLY from findings stored in the database
        by real detector runs, with redacted evidence.
        """
        dev_id = f"test-real-{uuid.uuid4().hex[:6]}"
        _create_test_device(dev_id, "Developer Workstation")
        headers = _get_admin_headers()

        sensitive_content = (
            "Configuration file:\n"
            "AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE\n"
            "AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY\n"
            "User contact: alice.developer@corp.com\n"
            "Credit card for billing: 4532-8921-3412-8910\n"
            "AI prompt: System Prompt for OpenAI ChatGPT model fine-tuning with customer secret."
        )

        # Trigger real scan with custom content
        scan_payload = {
            "custom_content": sensitive_content,
            "filename": "credentials_and_prompts.env",
            "destination": "EXTERNAL",
            "action": "UPLOAD",
        }
        scan_res = client.post(f"/api/devices/{dev_id}/scan", json=scan_payload, headers=headers)
        assert scan_res.status_code == 200
        scan_res.json()

        # 1. Verify findings are persisted in the database
        db = SessionLocal()
        try:
            persisted_findings = (
                db.query(Finding)
                .filter(Finding.device_id == dev_id)
                .all()
            )
            persisted_scan_logs = (
                db.query(ScanLog)
                .filter(ScanLog.device_id == dev_id)
                .all()
            )
            (
                db.query(Incident)
                .filter(Incident.device_id == dev_id)
                .all()
            )

            assert len(persisted_findings) >= 1, "Findings must be persisted in database"
            assert len(persisted_scan_logs) == 1, "ScanLog must be persisted in database"

            # Check that evidence is pre-redacted in the database
            for f in persisted_findings:
                assert f.evidence_redacted is not None
                # Zero plaintext secrets
                assert "AKIAIOSFODNN7EXAMPLE" not in f.evidence_redacted
                assert "4532-8921-3412-8910" not in f.evidence_redacted

            # 2. Query GET /api/devices/{dev_id}/scan-summary
            summary_res = client.get(f"/api/devices/{dev_id}/scan-summary", headers=headers)
            assert summary_res.status_code == 200
            summary = summary_res.json()

            # 3. Assert summary strictly equals persisted findings
            assert summary["has_scan_data"] is True
            assert summary["threats_detected"] == len(persisted_findings)
            assert summary["risk_score"] == max(sl.risk_score for sl in persisted_scan_logs)
            assert summary["user_information_count"] >= 1
            assert summary["ai_model_sharing_count"] >= 1
            assert summary["is_simulated"] is False

            # Check that scan_results in summary contains redacted evidence
            for sr in summary["scan_results"]:
                for finding in sr["findings"]:
                    assert "AKIAIOSFODNN7EXAMPLE" not in finding["matched_text"]
                    assert "4532-8921-3412-8910" not in finding["matched_text"]
        finally:
            db.close()

    def test_failed_scan_returns_error_never_allowed(self):
        """A failed or unreachable scan must return an error, never allowed or scan complete."""
        dev_id = f"test-err-{uuid.uuid4().hex[:6]}"
        _create_test_device(dev_id, "Remote Server")
        headers = _get_admin_headers()

        # Non-existent file path requested
        payload = {
            "file_path": "/nonexistent/path/to/missing_file.txt",
        }
        res = client.post(f"/api/devices/{dev_id}/scan", json=payload, headers=headers)
        assert res.status_code == 400
        assert "does not exist on disk" in res.json()["detail"]

    def test_simulation_gated_behind_demo_flag(self):
        """Simulation is forbidden in production path; only executed if demo flag is true."""
        from unittest.mock import patch

        dev_id = f"test-demo-{uuid.uuid4().hex[:6]}"
        _create_test_device(dev_id, "Cloud VM")
        headers = _get_admin_headers()

        # Clean environment without DEMO_MODE
        old_env = os.environ.get("DEMO_MODE")
        if "DEMO_MODE" in os.environ:
            del os.environ["DEMO_MODE"]

        try:
            with patch("os.walk", return_value=[]):
                # When demo=False and no filesystem files discovered:
                res_prod = client.post(
                    f"/api/devices/{dev_id}/scan",
                    json={"demo": False},
                    headers=headers,
                )
                assert res_prod.status_code == 200
                data_prod = res_prod.json()
                # Must return empty state without simulated findings
                assert data_prod["has_scan_data"] is False
                assert data_prod["risk_score"] is None
                assert data_prod["message"] == "No scan data yet"
                assert data_prod["is_simulated"] is False

                # When demo=True is explicitly passed and no filesystem files exist:
                res_demo = client.post(
                    f"/api/devices/{dev_id}/scan",
                    json={"demo": True},
                    headers=headers,
                )
                assert res_demo.status_code == 200
                data_demo = res_demo.json()
                assert data_demo["is_simulated"] is True

                # Confirm simulated findings are never saved as real Finding rows
                db = SessionLocal()
                try:
                    dev_findings = db.query(Finding).filter(Finding.device_id == dev_id).all()
                    assert len(dev_findings) == 0, "Simulated scan must never persist Finding rows"
                finally:
                    db.close()
        finally:
            if old_env is not None:
                os.environ["DEMO_MODE"] = old_env

    def test_non_admin_demo_flag_ignored_and_simulation_never_persists_findings(self):
        """
        1. Non-admin users sending demo=true must be ignored (treated as false) -> is_simulated=False.
        2. Admin users sending demo=true get is_simulated=True.
        3. Simulated results are clearly marked is_simulated=True and are NEVER saved as real Finding rows.
        4. DEMO_MODE env var still works for everyone (including non-admin).
        """
        from unittest.mock import patch

        old_env = os.environ.get("DEMO_MODE")
        if "DEMO_MODE" in os.environ:
            del os.environ["DEMO_MODE"]

        try:
            # 1. Non-admin user sending demo=True on their device
            analyst_dev_id = f"test-analyst-{uuid.uuid4().hex[:6]}"
            _create_analyst_device(analyst_dev_id, "Analyst Device")
            analyst_headers = _get_analyst_headers()

            with patch("os.walk", return_value=[]):
                res_analyst = client.post(
                    f"/api/devices/{analyst_dev_id}/scan",
                    json={"demo": True},
                    headers=analyst_headers,
                )
                assert res_analyst.status_code == 200
                data_analyst = res_analyst.json()
                # Non-admin demo=true MUST be ignored and treated as false
                assert data_analyst["is_simulated"] is False
                assert data_analyst["has_scan_data"] is False
                assert data_analyst["risk_score"] is None

            # 2. Admin sending demo=True
            admin_dev_id = f"test-admin-sim-{uuid.uuid4().hex[:6]}"
            _create_test_device(admin_dev_id, "Admin Device")
            admin_headers = _get_admin_headers()

            with patch("os.walk", return_value=[]):
                res_admin = client.post(
                    f"/api/devices/{admin_dev_id}/scan",
                    json={"demo": True},
                    headers=admin_headers,
                )
                assert res_admin.status_code == 200
                data_admin = res_admin.json()
                # Simulated results are clearly marked is_simulated=True
                assert data_admin["is_simulated"] is True
                assert data_admin["has_scan_data"] is True
                assert data_admin["risk_score"] is not None
                assert data_admin["threats_detected"] >= 1

                # 3. Confirm simulated results are NEVER saved as real Finding rows
                db = SessionLocal()
                try:
                    persisted_findings = (
                        db.query(Finding)
                        .filter(Finding.device_id == admin_dev_id)
                        .all()
                    )
                    assert len(persisted_findings) == 0, "Simulated results must never be saved as real Finding rows"

                    persisted_scan_logs = (
                        db.query(ScanLog)
                        .filter(ScanLog.device_id == admin_dev_id)
                        .all()
                    )
                    assert len(persisted_scan_logs) == 0, "Simulated results must never create ScanLog rows"

                    persisted_incidents = (
                        db.query(Incident)
                        .filter(Incident.device_id == admin_dev_id)
                        .all()
                    )
                    assert len(persisted_incidents) == 0, "Simulated results must never create Incident rows"
                finally:
                    db.close()

            # 4. DEMO_MODE env var still works for everyone (including non-admin)
            os.environ["DEMO_MODE"] = "true"
            try:
                with patch("os.walk", return_value=[]):
                    res_env_analyst = client.post(
                        f"/api/devices/{analyst_dev_id}/scan",
                        headers=analyst_headers,
                    )
                    assert res_env_analyst.status_code == 200
                    data_env = res_env_analyst.json()
                    assert data_env["is_simulated"] is True
            finally:
                del os.environ["DEMO_MODE"]
        finally:
            if old_env is not None:
                os.environ["DEMO_MODE"] = old_env
