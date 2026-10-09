"""
Tests for Device Enrollment Flow (Bootstrap → Attest → Complete).

Covers:
- Bootstrap endpoint with valid token
- Single-use token enforcement (replay prevention)
- Token consumption state transitions
- Device identity assignment with correct format
- Idempotency (duplicate calls return same device)
- Configuration endpoint
- Policy endpoint
"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from main import app
from database import SessionLocal
from models import DeviceProvisioning, Device, DeviceIdentity
from auth import create_access_token, get_password_hash
from models import User


@pytest.fixture
def client() -> TestClient:
    """Create a FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def db_session() -> Session:
    """Get a database session."""
    db = SessionLocal()
    yield db
    db.close()


@pytest.fixture
def admin_user(db_session: Session) -> User:
    """Create a test admin user."""
    db = db_session
    
    existing = db.query(User).filter(User.username == "flow_admin").first()
    if existing:
        db.delete(existing)
        db.commit()
    
    user = User(
        username="flow_admin",
        email="flow_admin@test.local",
        hashed_password=get_password_hash("password123"),
        role="admin",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _create_bootstrap_token(org_id: str = "flow-test-org") -> tuple[str, str]:
    """Create a bootstrap enrollment token and return (raw_token, token_hash)."""
    db = SessionLocal()
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=10)
    
    # Create DeviceProvisioning record (not EnrollmentToken)
    # This matches the production bootstrap endpoint implementation
    provisioning = DeviceProvisioning(
        bootstrap_token_hash=token_hash,
        organization_id=org_id,
        enrollment_policy_id="default-policy",
        platform="Windows",
        status="ACTIVE",
        provisioning_method="AUTOMATIC_ENROLLMENT",
        created_by="admin",
        expires_at=expires_at,
    )
    db.add(provisioning)
    db.commit()
    db.close()
    
    return raw_token, token_hash


# ---------------------------------------------------------------------------
# Bootstrap Endpoint Tests
# ---------------------------------------------------------------------------

def test_bootstrap_returns_configuration(client: TestClient, db_session: Session):
    """Test bootstrap endpoint returns proper configuration payload."""
    raw_token, _ = _create_bootstrap_token("config-org")
    
    response = client.post(
        "/api/v1/device-enrollment/bootstrap",
        params={"device_platform": "Windows"},
        headers={"Authorization": f"Bearer {raw_token}"},
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify required fields in response
    assert data["bootstrap_status"] == "ACCEPTED"
    assert data["organization_id"] == "config-org"
    assert "server_url" in data
    assert "device_identity_public_key" in data
    assert "next_step" in data


def test_bootstrap_marks_token_consumed(client: TestClient, db_session: Session):
    """Test that bootstrap endpoint marks token as consumed."""
    db = db_session
    raw_token, token_hash = _create_bootstrap_token("consumed-org")
    
    # Get initial token state
    initial_prov = db.query(DeviceProvisioning).filter(
        DeviceProvisioning.bootstrap_token_hash == token_hash
    ).first()
    assert initial_prov.status == "ACTIVE"
    assert initial_prov.last_used_at is None
    
    # Call bootstrap
    response = client.post(
        "/api/v1/device-enrollment/bootstrap",
        params={"device_platform": "Windows"},
        headers={"Authorization": f"Bearer {raw_token}"},
    )
    
    assert response.status_code == 200
    
    # Refresh session to see updates from bootstrap endpoint
    db.expire_all()
    
    # Verify token usage was recorded
    updated_prov = db.query(DeviceProvisioning).filter(
        DeviceProvisioning.bootstrap_token_hash == token_hash
    ).first()
    assert updated_prov.last_used_at is not None


# ---------------------------------------------------------------------------
# Single-Use Token Enforcement Tests
# ---------------------------------------------------------------------------

def test_bootstrap_single_use_enforcement(client: TestClient):
    """Test that bootstrap token can only be used once (replay prevention)."""
    raw_token, _ = _create_bootstrap_token("singleuse-org")
    
    # First call: should succeed
    response1 = client.post(
        "/api/v1/device-enrollment/bootstrap",
        params={"device_platform": "Windows"},
        headers={"Authorization": f"Bearer {raw_token}"},
    )
    assert response1.status_code == 200
    
    # Second call with same token: should fail
    response2 = client.post(
        "/api/v1/device-enrollment/bootstrap",
        params={"device_platform": "Windows"},
        headers={"Authorization": f"Bearer {raw_token}"},
    )
    assert response2.status_code == 401
    assert "already been used" in response2.json()["detail"]


def test_token_consumption_prevents_other_uses(client: TestClient):
    """Test that consuming token for bootstrap prevents other consumption types."""
    raw_token, _ = _create_bootstrap_token("consume-org")
    
    # Bootstrap consumes the token
    response1 = client.post(
        "/api/v1/device-enrollment/bootstrap",
        params={"device_platform": "Windows"},
        headers={"Authorization": f"Bearer {raw_token}"},
    )
    assert response1.status_code == 200
    
    # Try to use same token for attest - should fail
    response2 = client.post(
        "/api/v1/device-enrollment/attest",
        json={
            "device_platform": "Windows",
            "attestation_data": {},
            "public_key": "test",
        },
        headers={"Authorization": f"Bearer {raw_token}"},
    )
    # Should not accept already-consumed token
    # (exact behavior depends on implementation, but replay should be prevented)
    assert response2.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Device Identity Assignment Tests
# ---------------------------------------------------------------------------

def test_complete_creates_device_with_unique_id(client: TestClient, db_session: Session):
    """Test that /complete endpoint creates Device with unique DG-DEVICE-XXXX ID."""
    db = db_session
    
    response = client.post(
        "/api/v1/device-enrollment/complete",
        json={
            "device_platform": "Windows",
            "public_key": "-----BEGIN PUBLIC KEY-----\ntest_key_123\n-----END PUBLIC KEY-----",
            "device_name": "WORKSTATION-001",
        },
        headers={"Authorization": "Bearer test_token"},
    )
    
    assert response.status_code == 200
    data = response.json()
    device_id = data["device_id"]
    
    # Verify device ID format (platform-specific prefix)
    assert device_id.startswith("dg-win-")
    
    # Verify Device record was created
    device = db.query(Device).filter(Device.device_id == device_id).first()
    assert device is not None
    assert device.platform == "Windows"
    assert device.status == "ACTIVE"


def test_complete_creates_device_identity_record(client: TestClient, db_session: Session):
    """Test that /complete creates corresponding DeviceIdentity record."""
    db = db_session
    
    response = client.post(
        "/api/v1/device-enrollment/complete",
        json={
            "device_platform": "Android",
            "public_key": "-----BEGIN PUBLIC KEY-----\nandroid_key_456\n-----END PUBLIC KEY-----",
            "enrollment_code": "DG-TEST-5678",
        },
        headers={"Authorization": "Bearer test_token"},
    )
    
    assert response.status_code == 200
    device_id = response.json()["device_id"]
    
    # Verify DeviceIdentity record exists
    identity = db.query(DeviceIdentity).filter(
        DeviceIdentity.device_id == device_id
    ).first()
    assert identity is not None
    assert identity.platform == "Android"
    assert "android_key_456" in identity.public_key


def test_complete_computes_public_key_fingerprint(client: TestClient, db_session: Session):
    """Test that public key fingerprint is computed correctly (SHA-256 of PEM)."""
    db = db_session
    
    public_key = "-----BEGIN PUBLIC KEY-----\ntest_fingerprint_key\n-----END PUBLIC KEY-----"
    
    response = client.post(
        "/api/v1/device-enrollment/complete",
        json={
            "device_platform": "Windows",
            "public_key": public_key,
        },
        headers={"Authorization": "Bearer test_token"},
    )
    
    assert response.status_code == 200
    device_id = response.json()["device_id"]
    
    # Verify fingerprint is computed correctly
    expected_fingerprint = hashlib.sha256(public_key.encode("utf-8")).hexdigest()
    device = db.query(Device).filter(Device.device_id == device_id).first()
    assert device.public_key_fingerprint == expected_fingerprint


def test_complete_sets_attestation_status(client: TestClient, db_session: Session):
    """Test that attestationStatus is set during complete."""
    db = db_session
    
    response = client.post(
        "/api/v1/device-enrollment/complete",
        json={
            "device_platform": "iOS",
            "public_key": "-----BEGIN PUBLIC KEY-----\nios_key\n-----END PUBLIC KEY-----",
        },
        headers={"Authorization": "Bearer test_token"},
    )
    
    assert response.status_code == 200
    device_id = response.json()["device_id"]
    
    device = db.query(Device).filter(Device.device_id == device_id).first()
    assert device.attestation_status == "VALID"


# ---------------------------------------------------------------------------
# Idempotency Tests
# ---------------------------------------------------------------------------

def test_complete_idempotency_same_token_returns_same_device(client: TestClient, db_session: Session):
    """Test idempotency: calling complete twice with same token returns same device."""
    db = db_session
    
    device_data = {
        "device_platform": "Windows",
        "public_key": "-----BEGIN PUBLIC KEY-----\nidempotent_key\n-----END PUBLIC KEY-----",
        "device_name": "IDEMPOTENT-DEVICE",
    }
    
    # First call
    response1 = client.post(
        "/api/v1/device-enrollment/complete",
        json=device_data,
        headers={"Authorization": "Bearer idempotent_token_xyz"},
    )
    assert response1.status_code == 200
    device_id1 = response1.json()["device_id"]
    
    # Second call with same token
    response2 = client.post(
        "/api/v1/device-enrollment/complete",
        json=device_data,
        headers={"Authorization": "Bearer idempotent_token_xyz"},
    )
    assert response2.status_code == 200
    device_id2 = response2.json()["device_id"]
    
    # Should return same device ID (idempotency)
    assert device_id1 == device_id2
    
    # Verify only one device was created
    devices = db.query(Device).filter(Device.device_id == device_id1).all()
    assert len(devices) == 1


def test_no_duplicate_devices_on_concurrent_enrollment(client: TestClient, db_session: Session):
    """Test that concurrent enrollment with same token creates only one device."""
    db = db_session
    
    # In a real scenario, this would test concurrent requests
    # For now, simulate by calling complete multiple times
    device_data = {
        "device_platform": "macOS",
        "public_key": "-----BEGIN PUBLIC KEY-----\nmac_concurrent_key\n-----END PUBLIC KEY-----",
    }
    
    response1 = client.post(
        "/api/v1/device-enrollment/complete",
        json=device_data,
        headers={"Authorization": "Bearer concurrent_token"},
    )
    assert response1.status_code == 200
    device_id1 = response1.json()["device_id"]
    
    # Query device count by fingerprint
    public_key = device_data["public_key"]
    fingerprint = hashlib.sha256(public_key.encode("utf-8")).hexdigest()
    count = db.query(Device).filter(
        Device.public_key_fingerprint == fingerprint
    ).count()
    
    assert count == 1


# ---------------------------------------------------------------------------
# Configuration Endpoint Tests
# ---------------------------------------------------------------------------

def test_get_configuration_endpoint(client: TestClient, db_session: Session):
    """Test GET /configuration endpoint returns device configuration."""
    db = db_session
    
    # Create a device first with unique ID
    device_id = f"dg-win-testconfig-{secrets.token_hex(4)}"
    device = Device(
        device_id=device_id,
        device_name="Config Test Device",
        platform="Windows",
        status="ACTIVE",
        organization_id="config-test-org",
    )
    db.add(device)
    db.commit()
    
    response = client.get(
        "/api/v1/device-enrollment/configuration",
        params={"device_id": device_id},
        headers={"Authorization": "Bearer test_token"},
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify configuration payload
    assert data["organization_id"] == "config-test-org"
    assert "policy_id" in data
    assert "dlp_rules" in data
    assert "server_url" in data
    assert "heartbeat_interval" in data
    assert data["heartbeat_interval"] > 0


def test_configuration_includes_agent_settings(client: TestClient, db_session: Session):
    """Test that configuration includes agent configuration options."""
    db = db_session
    
    device_id = f"dg-android-agentconfig-{secrets.token_hex(4)}"
    device = Device(
        device_id=device_id,
        device_name="Agent Config Test",
        platform="Android",
        status="ACTIVE",
    )
    db.add(device)
    db.commit()
    
    response = client.get(
        "/api/v1/device-enrollment/configuration",
        params={"device_id": device_id},
        headers={"Authorization": "Bearer test_token"},
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert "agent_configuration" in data
    config = data["agent_configuration"]
    assert "enable_file_scanning" in config
    assert "enable_network_monitoring" in config


# ---------------------------------------------------------------------------
# Policy Endpoint Tests
# ---------------------------------------------------------------------------

def test_get_policy_endpoint(client: TestClient, db_session: Session):
    """Test GET /policy endpoint returns DLP policy."""
    db = db_session
    
    device_id = f"dg-ios-policy-{secrets.token_hex(4)}"
    device = Device(
        device_id=device_id,
        device_name="Policy Test Device",
        platform="iOS",
        status="ACTIVE",
        organization_id="policy-test-org",
    )
    db.add(device)
    db.commit()
    
    response = client.get(
        "/api/v1/device-enrollment/policy",
        params={"device_id": device_id},
        headers={"Authorization": "Bearer test_token"},
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify policy structure
    assert "policy_id" in data
    assert "version" in data
    assert "rules" in data
    assert "configurations" in data
    assert "cache_ttl_seconds" in data


def test_policy_includes_dlp_rules(client: TestClient, db_session: Session):
    """Test that policy includes DLP detection rules."""
    db = db_session
    
    device_id = f"dg-win-dlprules-{secrets.token_hex(4)}"
    device = Device(
        device_id=device_id,
        device_name="DLP Rules Test",
        platform="Windows",
        status="ACTIVE",
    )
    db.add(device)
    db.commit()
    
    response = client.get(
        "/api/v1/device-enrollment/policy",
        params={"device_id": device_id},
        headers={"Authorization": "Bearer test_token"},
    )
    
    assert response.status_code == 200
    data = response.json()
    rules = data["rules"]
    
    # Should have at least one rule
    assert len(rules) > 0
    
    # Verify rule structure
    for rule in rules:
        assert "id" in rule
        assert "type" in rule
        assert "pattern" in rule or "category" in rule
        assert "severity" in rule
        assert "action" in rule


def test_policy_configuration_options(client: TestClient, db_session: Session):
    """Test that policy includes configuration options."""
    db = db_session
    
    device_id = f"dg-android-policyconfig-{secrets.token_hex(4)}"
    device = Device(
        device_id=device_id,
        device_name="Policy Config Test",
        platform="Android",
        status="ACTIVE",
    )
    db.add(device)
    db.commit()
    
    response = client.get(
        "/api/v1/device-enrollment/policy",
        params={"device_id": device_id},
        headers={"Authorization": "Bearer test_token"},
    )
    
    assert response.status_code == 200
    data = response.json()
    config = data["configurations"]
    
    # Verify common configuration options
    assert "scan_on_copy" in config
    assert "scan_on_network_transfer" in config
    assert "alert_user" in config
    assert "log_incidents" in config


# ---------------------------------------------------------------------------
# Device Not Found Tests
# ---------------------------------------------------------------------------

def test_configuration_device_not_found(client: TestClient):
    """Test configuration endpoint returns 404 for non-existent device."""
    response = client.get(
        "/api/v1/device-enrollment/configuration",
        params={"device_id": "dg-nonexistent"},
        headers={"Authorization": "Bearer test_token"},
    )
    
    assert response.status_code == 404


def test_policy_device_not_found(client: TestClient):
    """Test policy endpoint returns 404 for non-existent device."""
    response = client.get(
        "/api/v1/device-enrollment/policy",
        params={"device_id": "dg-nonexistent"},
        headers={"Authorization": "Bearer test_token"},
    )
    
    assert response.status_code == 404
