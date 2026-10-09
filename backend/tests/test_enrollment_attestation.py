"""
Tests for Device Attestation Validation.

Covers:
- Valid attestation acceptance
- Invalid attestation rejection
- Missing attestation data (fallback behavior)
- Platform-specific attestation stubs (Android, iOS, Windows, macOS)
- AttestationStatus transitions
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from main import app
from database import SessionLocal
from models import Device


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


# ---------------------------------------------------------------------------
# Valid Attestation Tests
# ---------------------------------------------------------------------------

def test_attest_android_valid(client: TestClient):
    """Test Android attestation validation (stub)."""
    response = client.post(
        "/api/v1/device-enrollment/attest",
        json={
            "device_platform": "Android",
            "attestation_data": {
                "nonce": "test_nonce",
                "timestamp": 1234567890,
            },
            "public_key": "-----BEGIN PUBLIC KEY-----\nMIIBIjANBg...\n-----END PUBLIC KEY-----",
        },
        headers={"Authorization": "Bearer test_device_token"},
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["attestation_valid"] is True
    assert data["platform"] == "Android"
    assert "device_token" in data


def test_attest_ios_valid(client: TestClient):
    """Test iOS attestation validation (stub)."""
    response = client.post(
        "/api/v1/device-enrollment/attest",
        json={
            "device_platform": "iOS",
            "attestation_data": {
                "deviceToken": "test_ios_token",
                "challenge": "test_challenge",
            },
            "public_key": "-----BEGIN PUBLIC KEY-----\niOS_key\n-----END PUBLIC KEY-----",
        },
        headers={"Authorization": "Bearer test_device_token"},
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["attestation_valid"] is True
    assert data["platform"] == "iOS"


def test_attest_windows_valid(client: TestClient):
    """Test Windows attestation validation (stub)."""
    response = client.post(
        "/api/v1/device-enrollment/attest",
        json={
            "device_platform": "Windows",
            "attestation_data": {
                "aik_cert": "test_aik_cert",
                "tpm_version": "2.0",
            },
            "public_key": "-----BEGIN PUBLIC KEY-----\nwindows_tpm_key\n-----END PUBLIC KEY-----",
        },
        headers={"Authorization": "Bearer test_device_token"},
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["attestation_valid"] is True
    assert data["platform"] == "Windows"


def test_attest_macos_valid(client: TestClient):
    """Test macOS attestation validation (stub)."""
    response = client.post(
        "/api/v1/device-enrollment/attest",
        json={
            "device_platform": "macOS",
            "attestation_data": {
                "ecc_key": "test_ecc_key",
                "secure_enclave": True,
            },
            "public_key": "-----BEGIN PUBLIC KEY-----\nmac_key\n-----END PUBLIC KEY-----",
        },
        headers={"Authorization": "Bearer test_device_token"},
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["attestation_valid"] is True
    assert data["platform"] == "macOS"


# ---------------------------------------------------------------------------
# Attestation Failure Tests
# ---------------------------------------------------------------------------

def test_attest_missing_required_fields(client: TestClient):
    """Test attest with missing required fields."""
    response = client.post(
        "/api/v1/device-enrollment/attest",
        json={
            "device_platform": "Android",
            # Missing attestation_data and public_key
        },
        headers={"Authorization": "Bearer test_device_token"},
    )
    
    # Should return 422 or similar validation error
    assert response.status_code in (400, 422)


def test_attest_missing_device_token(client: TestClient):
    """Test attest without device token."""
    response = client.post(
        "/api/v1/device-enrollment/attest",
        json={
            "device_platform": "Android",
            "attestation_data": {},
            "public_key": "test",
        },
    )
    
    # Should require Authorization or device_token
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Attestation Status Transitions
# ---------------------------------------------------------------------------

def test_complete_sets_valid_attestation_status(client: TestClient, db_session: Session):
    """Test that complete endpoint sets attestationStatus to VALID."""
    db = db_session
    
    response = client.post(
        "/api/v1/device-enrollment/complete",
        json={
            "device_platform": "Windows",
            "public_key": "-----BEGIN PUBLIC KEY-----\ntest\n-----END PUBLIC KEY-----",
        },
        headers={"Authorization": "Bearer test_token"},
    )
    
    assert response.status_code == 200
    device_id = response.json()["device_id"]
    
    device = db.query(Device).filter(Device.device_id == device_id).first()
    assert device is not None
    assert device.attestation_status == "VALID"


def test_attestation_status_pending_on_creation(client: TestClient, db_session: Session):
    """Test that new devices can start with PENDING attestation status."""
    db = db_session
    
    # Create a device with PENDING status
    device = Device(
        device_id="dg-test-pending",
        device_name="Pending Attestation Device",
        platform="Android",
        status="ACTIVE",
        attestation_status="PENDING",
    )
    db.add(device)
    db.commit()
    
    # Verify status is PENDING
    retrieved = db.query(Device).filter(Device.device_id == "dg-test-pending").first()
    assert retrieved.attestation_status == "PENDING"


# ---------------------------------------------------------------------------
# Fallback Behavior (No Attestation Data)
# ---------------------------------------------------------------------------

def test_complete_without_attestation_data_accepted(client: TestClient):
    """Test that complete works even without platform attestation."""
    response = client.post(
        "/api/v1/device-enrollment/complete",
        json={
            "device_platform": "Windows",
            "public_key": "-----BEGIN PUBLIC KEY-----\nno_attestation_key\n-----END PUBLIC KEY-----",
        },
        headers={"Authorization": "Bearer test_token"},
    )
    
    # Should accept even without attestation (fallback behavior)
    assert response.status_code == 200
    assert "device_id" in response.json()


def test_attest_empty_attestation_data_accepted(client: TestClient):
    """Test attest with empty attestation data (fallback)."""
    response = client.post(
        "/api/v1/device-enrollment/attest",
        json={
            "device_platform": "iOS",
            "attestation_data": {},  # Empty
            "public_key": "-----BEGIN PUBLIC KEY-----\ntest\n-----END PUBLIC KEY-----",
        },
        headers={"Authorization": "Bearer test_device_token"},
    )
    
    # Should accept with fallback behavior
    assert response.status_code == 200
    assert response.json()["attestation_valid"] is True


# ---------------------------------------------------------------------------
# Platform-Specific Response Details
# ---------------------------------------------------------------------------

def test_attest_returns_platform_specific_details(client: TestClient):
    """Test that attest returns platform-specific attestation details."""
    response = client.post(
        "/api/v1/device-enrollment/attest",
        json={
            "device_platform": "Windows",
            "attestation_data": {"tpm": "2.0"},
            "public_key": "test_key",
        },
        headers={"Authorization": "Bearer test_token"},
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "attestation_details" in data
    assert "platform" in data["attestation_details"] or "Windows" in str(data.get("attestation_details", ""))


def test_attest_returns_next_step(client: TestClient):
    """Test that attest returns next_step in response."""
    response = client.post(
        "/api/v1/device-enrollment/attest",
        json={
            "device_platform": "Android",
            "attestation_data": {},
            "public_key": "test",
        },
        headers={"Authorization": "Bearer test_token"},
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "next_step" in data
    assert "complete" in data["next_step"].lower()


# ---------------------------------------------------------------------------
# Unknown Platform Handling
# ---------------------------------------------------------------------------

def test_attest_unknown_platform_accepted(client: TestClient):
    """Test that unknown platforms are accepted with fallback."""
    response = client.post(
        "/api/v1/device-enrollment/attest",
        json={
            "device_platform": "UnknownOS",
            "attestation_data": {},
            "public_key": "test",
        },
        headers={"Authorization": "Bearer test_token"},
    )
    
    # Should accept unknown platform for future extensibility
    assert response.status_code == 200
    data = response.json()
    assert data["attestation_valid"] is True


# ---------------------------------------------------------------------------
# Multiple Attestation Attempts
# ---------------------------------------------------------------------------

def test_multiple_attestation_calls_accepted(client: TestClient):
    """Test that device can call attest multiple times."""
    device_token = "multi_attest_token"
    
    # First call
    response1 = client.post(
        "/api/v1/device-enrollment/attest",
        json={
            "device_platform": "Windows",
            "attestation_data": {"attempt": 1},
            "public_key": "key1",
        },
        headers={"Authorization": f"Bearer {device_token}"},
    )
    assert response1.status_code == 200
    
    # Second call with updated data
    response2 = client.post(
        "/api/v1/device-enrollment/attest",
        json={
            "device_platform": "Windows",
            "attestation_data": {"attempt": 2},
            "public_key": "key1",
        },
        headers={"Authorization": f"Bearer {device_token}"},
    )
    assert response2.status_code == 200
    
    # Both should be valid
    assert response1.json()["attestation_valid"] is True
    assert response2.json()["attestation_valid"] is True


# ---------------------------------------------------------------------------
# Public Key Validation
# ---------------------------------------------------------------------------

def test_attest_malformed_public_key_still_accepted_at_stub(client: TestClient):
    """Test that attest still accepts malformed keys at stub stage."""
    response = client.post(
        "/api/v1/device-enrollment/attest",
        json={
            "device_platform": "Android",
            "attestation_data": {},
            "public_key": "not-a-valid-pem-key",
        },
        headers={"Authorization": "Bearer test_token"},
    )
    
    # At stub stage, should accept for testing
    # Production would validate PEM format
    assert response.status_code == 200
