"""
DataGhost - Agent Findings Ingestion & Remote Scan Trigger Tests.

Tests the integration between endpoint agents and backend:
1. POST /api/devices/{id}/scan sets scan_requested=True when no local files to scan.
2. POST /api/devices/{id}/heartbeat reflects scan_requested flag.
3. POST /api/devices/{id}/findings authenticates via Bearer device token.
4. POST /api/devices/{id}/findings ingests findings, creates ScanLog, Finding, and Incident records.
5. POST /api/devices/{id}/findings deduplicates identical findings by fingerprint.
6. Ingestion resets scan_requested to False.
"""
import hashlib
import secrets
import uuid
import pytest
from fastapi.testclient import TestClient

from main import app
from database import SessionLocal, init_db
from models import Device, Finding, Incident, ScanLog, User
from auth import create_access_token, get_password_hash

client = TestClient(app)


@pytest.fixture(autouse=True)
def ensure_db():
    init_db()


def _create_device_with_token(device_id: str, raw_token: str, scan_requested: bool = False) -> Device:
    db = SessionLocal()
    try:
        # Check or create default admin user
        admin = db.query(User).filter(User.username == "agent_test_admin").first()
        if not admin:
            admin = User(
                username="agent_test_admin",
                email="agent_test@local.net",
                hashed_password=get_password_hash("SecretPassword123!"),
                role="admin",
            )
            db.add(admin)
            db.commit()
            db.refresh(admin)

        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        dev = Device(
            device_id=device_id,
            device_name=f"Endpoint-{device_id[-6:]}",
            platform="Windows",
            status="ACTIVE",
            user_id=admin.id,
            device_token_hash=token_hash,
            auth_token=raw_token,
            scan_requested=scan_requested,
            files_scanned=0,
            incidents_count=0,
        )
        db.add(dev)
        db.commit()
        db.refresh(dev)
        return dev
    finally:
        db.close()


def test_heartbeat_and_scan_requested_flag():
    """Verify heartbeat reports scan_requested flag correctly."""
    dev_id = f"dg-test-{uuid.uuid4().hex[:8]}"
    raw_token = f"dg_dev_{secrets.token_urlsafe(24)}"
    _create_device_with_token(dev_id, raw_token, scan_requested=True)

    # Call heartbeat
    resp = client.post(
        f"/api/devices/{dev_id}/heartbeat",
        headers={"Authorization": f"Bearer {raw_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["scan_requested"] is True
    assert "ack_timestamp" in data


def test_device_scan_sets_scan_requested_when_no_local_files():
    """Triggering scan on endpoint without local files queues an agent scan."""
    dev_id = f"dg-test-{uuid.uuid4().hex[:8]}"
    raw_token = f"dg_dev_{secrets.token_urlsafe(24)}"
    _create_device_with_token(dev_id, raw_token, scan_requested=False)

    admin_token = create_access_token({"sub": "agent_test_admin", "role": "admin"})
    resp = client.post(
        f"/api/devices/{dev_id}/scan",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "Scan queued" in data.get("message", "")

    # Verify device record has scan_requested = True
    db = SessionLocal()
    try:
        dev = db.query(Device).filter(Device.device_id == dev_id).first()
        assert dev is not None
        assert dev.scan_requested is True
    finally:
        db.close()


def test_upload_findings_unauthorized_without_token():
    """Uploading findings without token or with invalid token must return 401."""
    dev_id = f"dg-test-{uuid.uuid4().hex[:8]}"
    raw_token = f"dg_dev_{secrets.token_urlsafe(24)}"
    _create_device_with_token(dev_id, raw_token)

    payload = {
        "scanned_files_count": 5,
        "total_bytes_scanned": 1024,
        "findings": [],
    }

    # No token
    res1 = client.post(f"/api/devices/{dev_id}/findings", json=payload)
    assert res1.status_code == 401

    # Invalid token
    res2 = client.post(
        f"/api/devices/{dev_id}/findings",
        json=payload,
        headers={"Authorization": "Bearer invalid_token_123"},
    )
    assert res2.status_code == 401


def test_upload_findings_success_and_records_created():
    """Valid findings upload persists ScanLog, Findings, Incidents, and updates counters."""
    dev_id = f"dg-test-{uuid.uuid4().hex[:8]}"
    raw_token = f"dg_dev_{secrets.token_urlsafe(24)}"
    _create_device_with_token(dev_id, raw_token, scan_requested=True)

    payload = {
        "scanned_files_count": 10,
        "total_bytes_scanned": 4096,
        "findings": [
            {
                "file_name": "passwords.txt",
                "file_path": "C:\\secure\\passwords.txt",
                "file_hash": "a1b2c3d4e5f6",
                "file_size": 256,
                "rule_id": "DATABASE_CREDENTIAL",
                "category": "CREDENTIALS",
                "severity": "CRITICAL",
                "confidence": 0.98,
                "line_number": 3,
                "column_number": 1,
                "char_start": 40,
                "char_end": 75,
                "evidence_redacted": "DB_PASSWORD=********",
                "description": "Exposed DB credentials",
                "remediation": "Move to secret manager",
            },
            {
                "file_name": "config.yaml",
                "file_path": "C:\\app\\config.yaml",
                "file_hash": "f6e5d4c3b2a1",
                "file_size": 512,
                "rule_id": "AWS_ACCESS_KEY",
                "category": "CLOUD",
                "severity": "HIGH",
                "confidence": 0.95,
                "line_number": 12,
                "column_number": 5,
                "char_start": 120,
                "char_end": 140,
                "evidence_redacted": "AKIA****************",
                "description": "AWS API key exposed",
                "remediation": "Rotate AWS IAM key",
            },
            {
                "file_name": "notes.md",
                "file_path": "C:\\notes.md",
                "file_hash": "998877665544",
                "file_size": 128,
                "rule_id": "INTERNAL_IP",
                "category": "NETWORK",
                "severity": "LOW",
                "confidence": 0.8,
                "line_number": 1,
                "column_number": 1,
                "char_start": 0,
                "char_end": 15,
                "evidence_redacted": "192.168.1.***",
                "description": "Internal IP reference",
                "remediation": "Informational",
            },
        ],
    }

    resp = client.post(
        f"/api/devices/{dev_id}/findings",
        json=payload,
        headers={"Authorization": f"Bearer {raw_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["device_id"] == dev_id
    assert data["persisted_findings_count"] == 3
    assert data["incidents_created_count"] == 2  # Only CRITICAL and HIGH create incidents

    db = SessionLocal()
    try:
        # Device counters updated
        dev = db.query(Device).filter(Device.device_id == dev_id).first()
        assert dev.files_scanned == 10
        assert dev.incidents_count == 2
        assert dev.scan_requested is False  # Reset on scan complete

        # Findings created in database
        findings = db.query(Finding).filter(Finding.device_id == dev_id).all()
        assert len(findings) == 3
        crit_finding = next(f for f in findings if f.severity == "CRITICAL")
        assert crit_finding.rule_id == "DATABASE_CREDENTIAL"
        assert crit_finding.evidence_redacted == "DB_PASSWORD=********"
        assert crit_finding.occurrence_count == 1

        # Incidents created
        incidents = db.query(Incident).filter(Incident.device_id == dev_id).all()
        assert len(incidents) == 2

        # ScanLog created
        slog = db.query(ScanLog).filter(ScanLog.device_id == dev_id).first()
        assert slog is not None
        assert slog.status == "COMPLETED"
        assert slog.is_simulated is False
    finally:
        db.close()


def test_upload_findings_deduplication():
    """Re-uploading the exact same finding increments occurrence_count without duplicate records."""
    dev_id = f"dg-test-{uuid.uuid4().hex[:8]}"
    raw_token = f"dg_dev_{secrets.token_urlsafe(24)}"
    _create_device_with_token(dev_id, raw_token)

    finding_item = {
        "file_name": "secrets.env",
        "file_path": "C:\\secrets.env",
        "file_hash": "abcdef123456",
        "file_size": 100,
        "rule_id": "STRIPE_KEY",
        "category": "CREDENTIALS",
        "severity": "HIGH",
        "confidence": 0.99,
        "line_number": 1,
        "column_number": 1,
        "char_start": 0,
        "char_end": 32,
        "evidence_redacted": "sk_live_****************",
    }

    payload = {
        "scanned_files_count": 1,
        "total_bytes_scanned": 100,
        "findings": [finding_item],
    }

    # Upload 1
    resp1 = client.post(
        f"/api/devices/{dev_id}/findings",
        json=payload,
        headers={"Authorization": f"Bearer {raw_token}"},
    )
    assert resp1.status_code == 200

    # Upload 2
    resp2 = client.post(
        f"/api/devices/{dev_id}/findings",
        json=payload,
        headers={"Authorization": f"Bearer {raw_token}"},
    )
    assert resp2.status_code == 200

    db = SessionLocal()
    try:
        findings = db.query(Finding).filter(Finding.device_id == dev_id).all()
        assert len(findings) == 1
        assert findings[0].occurrence_count == 2
    finally:
        db.close()
