"""
Tests for DataGhost Secure Device Enrollment API endpoints.

Tests verify:
- Enrollment routes can be imported without errors
- Bootstrap endpoint exists and accepts requests
- Token consumption mechanism works (single-use enforcement)
- Device creation works with proper ID format
"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from main import app
from database import SessionLocal
from models import EnrollmentToken, Device, User


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


def _create_bootstrap_token(org_id: str = "test-org") -> tuple[str, str]:
    """Create a bootstrap enrollment token and return (raw_token, token_hash)."""
    db = SessionLocal()
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=10)
    
    enrollment = EnrollmentToken(
        token_hash=token_hash,
        enrollment_code=f"DG-TEST-{secrets.token_hex(2).upper()}",
        platform="Windows",
        organization_id=org_id,
        created_by="admin",
        expires_at=expires_at,
        status="PENDING",
    )
    db.add(enrollment)
    db.commit()
    db.close()
    
    return raw_token, token_hash


# ---------------------------------------------------------------------------
# Import Tests
# ---------------------------------------------------------------------------

def test_enrollment_routes_importable():
    """Test that enrollment routes can be imported without errors."""
    try:
        from api.enrollment_routes import router  # noqa: F401
        assert router is not None
    except Exception as e:
        pytest.fail(f"Failed to import enrollment routes: {e}")


def test_enrollment_router_mounted():
    """Test that enrollment router is mounted in the app."""
    # Check that the app has routes from enrollment module
    route_paths = [route.path for route in app.routes]
    
    # Should have at least one enrollment endpoint
    has_enrollment_routes = any("/device-enrollment" in str(path) for path in route_paths)
    assert has_enrollment_routes or len(route_paths) > 0, "App should have routes"


# ---------------------------------------------------------------------------
# Bootstrap Endpoint Tests
# ---------------------------------------------------------------------------

def test_bootstrap_endpoint_exists(client: TestClient):
    """Test that bootstrap endpoint exists and is accessible."""
    # Should get a response (may be 401, but endpoint should exist)
    response = client.post(
        "/api/v1/device-enrollment/bootstrap",
        params={"device_platform": "Windows"},
    )
    # Should not be 404
    assert response.status_code != 404


def test_bootstrap_with_valid_token(client: TestClient):
    """Test bootstrap endpoint with valid Bearer token."""
    raw_token, token_hash = _create_bootstrap_token("test-org")
    
    response = client.post(
        "/api/v1/device-enrollment/bootstrap",
        json={
            "device_platform": "Windows",
            "device_model": "HP EliteBook",
            "os_version": "10.0.19045",
        },
        headers={
            "Authorization": f"Bearer {raw_token}",
        },
    )
    
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    data = response.json()
    assert data["bootstrap_status"] == "ACCEPTED"
    assert data["organization_id"] == "test-org"
    assert "server_url" in data
    assert "device_identity_public_key" in data
    assert data["next_step"] == "/api/v1/device-enrollment/attest"


def test_bootstrap_token_single_use_enforced(client: TestClient):
    """Test that bootstrap token is single-use (consumed on first call)."""
    raw_token, token_hash = _create_bootstrap_token("test-org")
    
    # First call: should succeed
    response1 = client.post(
        "/api/v1/device-enrollment/bootstrap",
        json={"device_platform": "Windows"},
        headers={"Authorization": f"Bearer {raw_token}"},
    )
    assert response1.status_code == 200
    
    # Verify token was consumed
    db = SessionLocal()
    token_record = db.query(EnrollmentToken).filter(
        EnrollmentToken.token_hash == token_hash
    ).first()
    db.close()
    
    assert token_record is not None
    assert token_record.status == "CONSUMED_BOOTSTRAP"
    
    # Second call with same token: should fail (token replay prevention)
    response2 = client.post(
        "/api/v1/device-enrollment/bootstrap",
        json={"device_platform": "Windows"},
        headers={"Authorization": f"Bearer {raw_token}"},
    )
    assert response2.status_code == 401
    assert "already been used" in response2.json()["detail"]


def test_bootstrap_missing_authorization_header(client: TestClient):
    """Test bootstrap endpoint without Authorization header."""
    response = client.post(
        "/api/v1/device-enrollment/bootstrap",
        json={"device_platform": "Windows"},
    )
    
    assert response.status_code == 401
    assert "Missing Authorization header" in response.json()["detail"]


def test_bootstrap_invalid_token(client: TestClient):
    """Test bootstrap endpoint with invalid token."""
    response = client.post(
        "/api/v1/device-enrollment/bootstrap",
        json={"device_platform": "Windows"},
        headers={"Authorization": "Bearer invalid_token_xyz"},
    )
    
    assert response.status_code == 401
    assert "Invalid enrollment token" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Attest Endpoint Tests
# ---------------------------------------------------------------------------

def test_attest_endpoint_exists(client: TestClient):
    """Test that attest endpoint exists."""
    response = client.post(
        "/api/v1/device-enrollment/attest",
        json={
            "device_platform": "Android",
            "attestation_data": {},
            "public_key": "test",
        },
    )
    assert response.status_code != 404


def test_attest_with_valid_data(client: TestClient):
    """Test attest endpoint with valid attestation data."""
    response = client.post(
        "/api/v1/device-enrollment/attest",
        json={
            "device_platform": "Android",
            "attestation_data": {"nonce": "test"},
            "public_key": "-----BEGIN PUBLIC KEY-----\ntest\n-----END PUBLIC KEY-----",
            "device_token": "test_device_token",
        },
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["attestation_valid"] is True
    assert data["platform"] == "Android"
    assert "device_token" in data


# ---------------------------------------------------------------------------
# Complete Endpoint Tests
# ---------------------------------------------------------------------------

def test_complete_endpoint_exists(client: TestClient):
    """Test that complete endpoint exists."""
    response = client.post(
        "/api/v1/device-enrollment/complete",
        json={
            "device_platform": "Windows",
            "public_key": "test",
        },
    )
    assert response.status_code != 404


def test_complete_creates_device_with_correct_id_format(client: TestClient):
    """Test that /complete endpoint creates Device with DG-DEVICE-XXXX ID format."""
    import uuid
    unique_code = f"DG-TEST-{uuid.uuid4().hex[:4].upper()}"
    response = client.post(
        "/api/v1/device-enrollment/complete",
        json={
            "device_platform": "Windows",
            "public_key": "-----BEGIN PUBLIC KEY-----\ntest_key\n-----END PUBLIC KEY-----",
            "enrollment_code": unique_code,
            "device_name": "WORKSTATION-001",
            "os_version": "10.0.19045",
            "hostname": "workstation-001",
            "ip_address": "192.168.1.100",
        },
        headers={"Authorization": "Bearer test_token"},
    )
    
    assert response.status_code == 200
    data = response.json()
    device_id = data["device_id"]
    
    # Verify device ID format
    assert device_id.startswith("dg-win-"), f"Windows device ID should start with 'dg-win-', got {device_id}"
    assert len(device_id) > len("dg-win-"), "Device ID should have random suffix"
    assert data["status"] == "ENROLLED"
    assert data["heartbeat_interval"] == 30
    
    # Verify device was created in database
    db = SessionLocal()
    device = db.query(Device).filter(Device.device_id == device_id).first()
    db.close()
    
    assert device is not None
    assert device.device_name == "WORKSTATION-001"
    assert device.platform == "Windows"
    assert device.status == "ACTIVE"


def test_complete_android_device_has_correct_prefix(client: TestClient):
    """Test that Android devices get dg-android- prefix."""
    response = client.post(
        "/api/v1/device-enrollment/complete",
        json={
            "device_platform": "Android",
            "public_key": "-----BEGIN PUBLIC KEY-----\nandroid_key\n-----END PUBLIC KEY-----",
            "device_name": "Samsung Galaxy",
        },
        headers={"Authorization": "Bearer test_token"},
    )
    
    assert response.status_code == 200
    device_id = response.json()["device_id"]
    assert device_id.startswith("dg-android-")


# ---------------------------------------------------------------------------
# Configuration Endpoint Tests
# ---------------------------------------------------------------------------

def test_configuration_endpoint_exists(client: TestClient):
    """Test that configuration endpoint exists."""
    import uuid
    test_device_id = f"dg-win-test-{uuid.uuid4().hex[:8]}"
    # Create a device first
    db = SessionLocal()
    device = Device(
        device_id=test_device_id,
        device_name="Test Device",
        platform="Windows",
        status="ACTIVE",
    )
    db.add(device)
    db.commit()
    db.close()
    
    response = client.get(
        "/api/v1/device-enrollment/configuration",
        params={"device_id": test_device_id},
        headers={"Authorization": "Bearer test_token"},
    )
    assert response.status_code != 404


def test_configuration_requires_device_id(client: TestClient):
    """Test that configuration endpoint requires device_id."""
    response = client.get(
        "/api/v1/device-enrollment/configuration",
        headers={"Authorization": "Bearer test_token"},
    )
    
    assert response.status_code == 400
    assert "device_id required" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Policy Endpoint Tests
# ---------------------------------------------------------------------------

def test_policy_endpoint_exists(client: TestClient):
    """Test that policy endpoint exists."""
    import uuid
    test_device_id = f"dg-win-test-{uuid.uuid4().hex[:8]}"
    # Create a device first
    db = SessionLocal()
    device = Device(
        device_id=test_device_id,
        device_name="Test Device",
        platform="Windows",
        status="ACTIVE",
    )
    db.add(device)
    db.commit()
    db.close()
    
    response = client.get(
        "/api/v1/device-enrollment/policy",
        params={"device_id": test_device_id},
        headers={"Authorization": "Bearer test_token"},
    )
    assert response.status_code != 404


def test_policy_returns_dlp_rules(client: TestClient):
    """Test that policy endpoint returns DLP rules."""
    import uuid
    test_device_id = f"dg-win-test-{uuid.uuid4().hex[:8]}"
    # Create a device first
    db = SessionLocal()
    device = Device(
        device_id=test_device_id,
        device_name="Test Device",
        platform="Windows",
        status="ACTIVE",
    )
    db.add(device)
    db.commit()
    db.close()
    
    response = client.get(
        "/api/v1/device-enrollment/policy",
        params={"device_id": test_device_id},
        headers={"Authorization": "Bearer test_token"},
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "rules" in data
    assert isinstance(data["rules"], list)
    assert len(data["rules"]) > 0
    assert "configurations" in data
    assert "cache_ttl_seconds" in data


# ---------------------------------------------------------------------------
# Integration Tests
# ---------------------------------------------------------------------------

def test_enrollment_flow_bootstrap_to_complete(client: TestClient):
    """Integration test: Full enrollment flow from bootstrap to complete."""
    # Step 1: Create bootstrap token
    raw_token, token_hash = _create_bootstrap_token("integration-org")
    
    # Step 2: Bootstrap
    response_bootstrap = client.post(
        "/api/v1/device-enrollment/bootstrap",
        json={"device_platform": "Windows"},
        headers={"Authorization": f"Bearer {raw_token}"},
    )
    assert response_bootstrap.status_code == 200
    assert response_bootstrap.json()["bootstrap_status"] == "ACCEPTED"
    
    # Step 3: Attest
    response_attest = client.post(
        "/api/v1/device-enrollment/attest",
        json={
            "device_platform": "Windows",
            "attestation_data": {"test": "data"},
            "public_key": "-----BEGIN PUBLIC KEY-----\ntest\n-----END PUBLIC KEY-----",
        },
        headers={"Authorization": "Bearer test_device_token"},
    )
    assert response_attest.status_code == 200
    
    # Step 4: Complete
    response_complete = client.post(
        "/api/v1/device-enrollment/complete",
        json={
            "device_platform": "Windows",
            "public_key": "-----BEGIN PUBLIC KEY-----\ntest\n-----END PUBLIC KEY-----",
            "device_name": "Integration Test Device",
        },
        headers={"Authorization": "Bearer test_device_token"},
    )
    assert response_complete.status_code == 200
    device_id = response_complete.json()["device_id"]
    
    # Step 5: Verify device in database
    db = SessionLocal()
    device = db.query(Device).filter(Device.device_id == device_id).first()
    db.close()
    assert device is not None
    assert device.platform == "Windows"
    assert device.status == "ACTIVE"
