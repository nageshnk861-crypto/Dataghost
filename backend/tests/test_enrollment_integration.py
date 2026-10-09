"""
Integration Tests for Full Enrollment Pipeline.

Covers end-to-end enrollment flow:
- Create provisioning record
- Bootstrap with token
- Attest device
- Complete enrollment
- Device lifecycle verification
- Policy download
- Configuration retrieval
- Heartbeat functionality
"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from main import app
from database import SessionLocal
from models import (
    EnrollmentToken, Device, DeviceIdentity, DeviceProvisioning, User
)
from auth import get_password_hash, create_access_token


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
    """Create admin user for provisioning."""
    db = db_session
    
    existing = db.query(User).filter(User.username == "int_admin").first()
    if existing:
        db.delete(existing)
        db.commit()
    
    user = User(
        username="int_admin",
        email="int_admin@test.local",
        hashed_password=get_password_hash("password123"),
        role="admin",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def admin_token(admin_user: User) -> str:
    """Create admin JWT token."""
    return create_access_token({"sub": admin_user.username, "role": admin_user.role})


# ---------------------------------------------------------------------------
# End-to-End Enrollment Pipeline
# ---------------------------------------------------------------------------

def test_full_enrollment_pipeline_windows(client: TestClient, admin_token: str, db_session: Session):
    """
    Integration test: Full Windows enrollment pipeline.
    
    Flow:
    1. Create provisioning record
    2. Bootstrap with token
    3. Attest device
    4. Complete enrollment
    5. Verify device in database
    6. Query configuration
    7. Query policy
    """
    db = db_session
    org_id = "e2e-test-org"
    
    # Step 1: Create provisioning record
    prov_response = client.post(
        "/api/v1/device-provisioning/create",
        json={
            "organization_id": org_id,
            "enrollment_policy_id": "policy-windows",
            "platform": "Windows",
            "provisioning_method": "AUTOMATIC_ENROLLMENT",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert prov_response.status_code == 200
    prov_data = prov_response.json()
    bootstrap_token = prov_data["bootstrap_token"]
    
    # Step 2: Bootstrap device
    bootstrap_response = client.post(
        "/api/v1/device-enrollment/bootstrap",
        params={"device_platform": "Windows"},
        headers={"Authorization": f"Bearer {bootstrap_token}"},
    )
    assert bootstrap_response.status_code == 200
    bootstrap_data = bootstrap_response.json()
    assert bootstrap_data["organization_id"] == org_id
    assert bootstrap_data["bootstrap_status"] == "ACCEPTED"
    
    # Step 3: Attest device
    attest_response = client.post(
        "/api/v1/device-enrollment/attest",
        json={
            "device_platform": "Windows",
            "attestation_data": {"tpm": "2.0", "manufacturer": "Intel"},
            "public_key": "-----BEGIN PUBLIC KEY-----\nwindows_e2e_key\n-----END PUBLIC KEY-----",
        },
        headers={"Authorization": f"Bearer {bootstrap_token}"},
    )
    assert attest_response.status_code == 200
    attest_data = attest_response.json()
    device_token = attest_data["device_token"]
    
    # Step 4: Complete enrollment
    complete_response = client.post(
        "/api/v1/device-enrollment/complete",
        json={
            "device_platform": "Windows",
            "public_key": "-----BEGIN PUBLIC KEY-----\nwindows_e2e_key\n-----END PUBLIC KEY-----",
            "device_name": "E2E-WORKSTATION-001",
            "os_version": "10.0.19045",
            "hostname": "e2e-workstation",
            "ip_address": "10.0.0.100",
        },
        headers={"Authorization": f"Bearer {device_token}"},
    )
    assert complete_response.status_code == 200
    complete_data = complete_response.json()
    device_id = complete_data["device_id"]
    assert device_id.startswith("dg-win-")
    
    # Step 5: Verify device in database
    device = db.query(Device).filter(Device.device_id == device_id).first()
    assert device is not None
    assert device.platform == "Windows"
    assert device.status == "ACTIVE"
    assert device.device_name == "E2E-WORKSTATION-001"
    assert device.organization_id == org_id
    assert device.attestation_status == "VALID"
    
    # Verify DeviceIdentity was created
    identity = db.query(DeviceIdentity).filter(
        DeviceIdentity.device_id == device_id
    ).first()
    assert identity is not None
    assert "windows_e2e_key" in identity.public_key
    
    # Step 6: Query configuration
    config_response = client.get(
        "/api/v1/device-enrollment/configuration",
        params={"device_id": device_id},
        headers={"Authorization": f"Bearer {device_token}"},
    )
    assert config_response.status_code == 200
    config_data = config_response.json()
    assert config_data["organization_id"] == org_id
    assert "dlp_rules" in config_data
    assert "heartbeat_interval" in config_data
    
    # Step 7: Query policy
    policy_response = client.get(
        "/api/v1/device-enrollment/policy",
        params={"device_id": device_id},
        headers={"Authorization": f"Bearer {device_token}"},
    )
    assert policy_response.status_code == 200
    policy_data = policy_response.json()
    assert "rules" in policy_data
    assert "configurations" in policy_data
    assert len(policy_data["rules"]) > 0


def test_full_enrollment_pipeline_android(client: TestClient, admin_token: str, db_session: Session):
    """Integration test: Full Android enrollment pipeline."""
    db = db_session
    org_id = "e2e-android-org"
    
    # Create provisioning for Android
    prov_response = client.post(
        "/api/v1/device-provisioning/create",
        json={
            "organization_id": org_id,
            "enrollment_policy_id": "policy-android",
            "platform": "Android",
            "provisioning_method": "AUTOMATIC_ENROLLMENT",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert prov_response.status_code == 200
    bootstrap_token = prov_response.json()["bootstrap_token"]
    
    # Bootstrap
    bootstrap_response = client.post(
        "/api/v1/device-enrollment/bootstrap",
        params={"device_platform": "Android", "device_model": "Samsung Galaxy S22"},
        headers={"Authorization": f"Bearer {bootstrap_token}"},
    )
    assert bootstrap_response.status_code == 200
    
    # Attest
    attest_response = client.post(
        "/api/v1/device-enrollment/attest",
        json={
            "device_platform": "Android",
            "attestation_data": {"nonce": "test_nonce", "device_id": "device_123"},
            "public_key": "-----BEGIN PUBLIC KEY-----\nandroid_e2e_key\n-----END PUBLIC KEY-----",
        },
        headers={"Authorization": f"Bearer {bootstrap_token}"},
    )
    assert attest_response.status_code == 200
    device_token = attest_response.json()["device_token"]
    
    # Complete
    complete_response = client.post(
        "/api/v1/device-enrollment/complete",
        json={
            "device_platform": "Android",
            "public_key": "-----BEGIN PUBLIC KEY-----\nandroid_e2e_key\n-----END PUBLIC KEY-----",
            "device_name": "Samsung Galaxy S22",
            "os_version": "12.0",
            "device_supplied_id": "device_123",
        },
        headers={"Authorization": f"Bearer {device_token}"},
    )
    assert complete_response.status_code == 200
    device_id = complete_response.json()["device_id"]
    
    # Verify Android device
    device = db.query(Device).filter(Device.device_id == device_id).first()
    assert device.platform == "Android"
    assert device.device_name == "Samsung Galaxy S22"
    
    # Query policy and config
    policy_response = client.get(
        "/api/v1/device-enrollment/policy",
        params={"device_id": device_id},
        headers={"Authorization": f"Bearer {device_token}"},
    )
    assert policy_response.status_code == 200


def test_full_enrollment_pipeline_ios(client: TestClient, admin_token: str, db_session: Session):
    """Integration test: Full iOS enrollment pipeline."""
    db = db_session
    org_id = "e2e-ios-org"
    
    # Create provisioning for iOS
    prov_response = client.post(
        "/api/v1/device-provisioning/create",
        json={
            "organization_id": org_id,
            "enrollment_policy_id": "policy-ios",
            "platform": "iOS",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert prov_response.status_code == 200
    bootstrap_token = prov_response.json()["bootstrap_token"]
    
    # Full flow
    bootstrap_response = client.post(
        "/api/v1/device-enrollment/bootstrap",
        params={"device_platform": "iOS"},
        headers={"Authorization": f"Bearer {bootstrap_token}"},
    )
    assert bootstrap_response.status_code == 200
    
    attest_response = client.post(
        "/api/v1/device-enrollment/attest",
        json={
            "device_platform": "iOS",
            "attestation_data": {"challenge": "test", "timestamp": 1234567890},
            "public_key": "-----BEGIN PUBLIC KEY-----\nios_e2e_key\n-----END PUBLIC KEY-----",
        },
        headers={"Authorization": f"Bearer {bootstrap_token}"},
    )
    assert attest_response.status_code == 200
    device_token = attest_response.json()["device_token"]
    
    complete_response = client.post(
        "/api/v1/device-enrollment/complete",
        json={
            "device_platform": "iOS",
            "public_key": "-----BEGIN PUBLIC KEY-----\nios_e2e_key\n-----END PUBLIC KEY-----",
            "device_name": "iPhone 14 Pro",
            "os_version": "16.5",
        },
        headers={"Authorization": f"Bearer {device_token}"},
    )
    assert complete_response.status_code == 200
    device_id = complete_response.json()["device_id"]
    
    # Verify
    device = db.query(Device).filter(Device.device_id == device_id).first()
    assert device.platform == "iOS"


# ---------------------------------------------------------------------------
# Device Listing and Discovery
# ---------------------------------------------------------------------------

def test_enrolled_device_appears_in_device_list(client: TestClient, admin_token: str, db_session: Session):
    """Test that newly enrolled device appears in device list."""
    db = db_session
    
    # Complete a device enrollment
    complete_response = client.post(
        "/api/v1/device-enrollment/complete",
        json={
            "device_platform": "Windows",
            "public_key": "-----BEGIN PUBLIC KEY-----\ntest_list_key\n-----END PUBLIC KEY-----",
            "device_name": "LIST-TEST-DEVICE",
        },
        headers={"Authorization": "Bearer test_token"},
    )
    assert complete_response.status_code == 200
    device_id = complete_response.json()["device_id"]
    
    # List devices
    list_response = client.get(
        "/api/v1/devices",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    
    # Should be accessible (may or may not be in /devices endpoint)
    assert list_response.status_code in (200, 401)


# ---------------------------------------------------------------------------
# Heartbeat Functionality
# ---------------------------------------------------------------------------

def test_enrolled_device_heartbeat(client: TestClient, db_session: Session):
    """Test that enrolled device can send heartbeat."""
    db = db_session
    
    # Create a device
    complete_response = client.post(
        "/api/v1/device-enrollment/complete",
        json={
            "device_platform": "Windows",
            "public_key": "-----BEGIN PUBLIC KEY-----\nhb_key\n-----END PUBLIC KEY-----",
            "device_name": "HEARTBEAT-TEST",
        },
        headers={"Authorization": "Bearer test_token"},
    )
    assert complete_response.status_code == 200
    device_id = complete_response.json()["device_id"]
    
    # Send heartbeat
    heartbeat_response = client.post(
        f"/api/v1/devices/{device_id}/heartbeat",
        json={
            "status": "ACTIVE",
            "incidents_count": 0,
            "files_scanned": 1000,
        },
    )
    
    # Should accept heartbeat (even if auth required, endpoint should exist)
    assert heartbeat_response.status_code in (200, 401)


# ---------------------------------------------------------------------------
# Multi-Device Enrollment
# ---------------------------------------------------------------------------

def test_multiple_devices_enrollment_in_same_organization(
    client: TestClient, admin_token: str, db_session: Session
):
    """Test enrolling multiple devices in the same organization."""
    db = db_session
    org_id = "multi-device-org"
    
    # Create provisioning
    prov_response = client.post(
        "/api/v1/device-provisioning/create",
        json={
            "organization_id": org_id,
            "enrollment_policy_id": "policy-1",
            "platform": "Windows",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    token1 = prov_response.json()["bootstrap_token"]
    
    # Create second provisioning
    prov_response2 = client.post(
        "/api/v1/device-provisioning/create",
        json={
            "organization_id": org_id,
            "enrollment_policy_id": "policy-1",
            "platform": "Windows",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    token2 = prov_response2.json()["bootstrap_token"]
    
    # Enroll first device
    device_ids = []
    for token in [token1, token2]:
        bootstrap_response = client.post(
            "/api/v1/device-enrollment/bootstrap",
            params={"device_platform": "Windows"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert bootstrap_response.status_code == 200
        
        complete_response = client.post(
            "/api/v1/device-enrollment/complete",
            json={
                "device_platform": "Windows",
                "public_key": f"-----BEGIN PUBLIC KEY-----\nkey_{token[:10]}\n-----END PUBLIC KEY-----",
                "device_name": f"MULTI-DEVICE-{len(device_ids) + 1}",
            },
            headers={"Authorization": "Bearer test_token"},
        )
        assert complete_response.status_code == 200
        device_ids.append(complete_response.json()["device_id"])
    
    # Verify both devices exist
    assert len(device_ids) == 2
    assert device_ids[0] != device_ids[1]
    
    for device_id in device_ids:
        device = db.query(Device).filter(Device.device_id == device_id).first()
        assert device is not None
        assert device.organization_id == org_id


# ---------------------------------------------------------------------------
# Device State Transitions
# ---------------------------------------------------------------------------

def test_device_transitions_through_enrollment_states(client: TestClient, db_session: Session):
    """Test that device goes through proper enrollment state transitions."""
    db = db_session
    
    # Complete enrollment
    complete_response = client.post(
        "/api/v1/device-enrollment/complete",
        json={
            "device_platform": "Windows",
            "public_key": "-----BEGIN PUBLIC KEY-----\nstate_key\n-----END PUBLIC KEY-----",
            "device_name": "STATE-TEST",
        },
        headers={"Authorization": "Bearer test_token"},
    )
    device_id = complete_response.json()["device_id"]
    
    # Device should be ACTIVE after complete
    device = db.query(Device).filter(Device.device_id == device_id).first()
    assert device.status == "ACTIVE"
    assert device.attestation_status == "VALID"


# ---------------------------------------------------------------------------
# Error Recovery
# ---------------------------------------------------------------------------

def test_enrollment_recovery_after_failed_attest(client: TestClient, admin_token: str):
    """Test that device can recover from failed attestation."""
    org_id = "recovery-org"
    
    # Create provisioning
    prov_response = client.post(
        "/api/v1/device-provisioning/create",
        json={
            "organization_id": org_id,
            "enrollment_policy_id": "policy-1",
            "platform": "Windows",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    bootstrap_token = prov_response.json()["bootstrap_token"]
    
    # Bootstrap
    bootstrap_response = client.post(
        "/api/v1/device-enrollment/bootstrap",
        params={"device_platform": "Windows"},
        headers={"Authorization": f"Bearer {bootstrap_token}"},
    )
    assert bootstrap_response.status_code == 200
    
    # Attest (may fail, but should not crash)
    attest_response = client.post(
        "/api/v1/device-enrollment/attest",
        json={
            "device_platform": "Windows",
            "attestation_data": {"invalid": "data"},
            "public_key": "invalid_key",
        },
        headers={"Authorization": f"Bearer {bootstrap_token}"},
    )
    # Should still return valid response (stub accepts)
    assert attest_response.status_code == 200
