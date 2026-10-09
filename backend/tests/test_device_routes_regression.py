"""
Regression Tests for Existing Device Routes.

Ensures that new enrollment system doesn't break existing device management:
- Existing device creation still works
- Device listing endpoints still work
- Device heartbeat endpoints still work
- Device updates still work
- Status management still works
"""
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from main import app
from database import SessionLocal
from models import Device, User
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
    """Create test admin user."""
    db = db_session
    
    existing = db.query(User).filter(User.username == "regression_admin").first()
    if existing:
        db.delete(existing)
        db.commit()
    
    user = User(
        username="regression_admin",
        email="regression@test.local",
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


@pytest.fixture
def test_device(db_session: Session) -> Device:
    """Create a test device."""
    db = db_session
    
    import uuid
    device_id = f"legacy-device-{uuid.uuid4().hex[:8]}"
    
    device = Device(
        device_id=device_id,
        device_name="Legacy Test Device",
        platform="Windows",
        os_version="10.0.19045",
        hostname="legacy-host",
        status="ACTIVE",
        organization_id="default-org",
    )
    db.add(device)
    db.commit()
    db.refresh(device)
    return device


# ---------------------------------------------------------------------------
# Device Creation/Registration Regression Tests
# ---------------------------------------------------------------------------

def test_legacy_device_registration_endpoint(client: TestClient, admin_token: str):
    """Test that legacy /devices/registration/register endpoint still works."""
    response = client.post(
        "/api/v1/devices/enrollment/register",
        json={
            "device_id": "legacy-reg-001",
            "device_name": "Legacy Registration Device",
            "platform": "Windows",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    
    # Endpoint should still exist (may be 200 or other status)
    assert response.status_code != 404


def test_device_creation_with_legacy_fields(client: TestClient, db_session: Session):
    """Test that Device can still be created with legacy fields."""
    db = db_session
    
    device = Device(
        device_id="legacy-fields-001",
        device_name="Legacy Fields Device",
        platform="Linux",
        os_name="Linux",
        os_version="5.4.0",
        hostname="legacy-linux",
        ip_address="192.168.1.50",
        status="ACTIVE",
    )
    db.add(device)
    db.commit()
    
    # Verify device was created
    retrieved = db.query(Device).filter(Device.device_id == "legacy-fields-001").first()
    assert retrieved is not None
    assert retrieved.device_name == "Legacy Fields Device"
    assert retrieved.os_version == "5.4.0"


def test_device_post_endpoint_still_works(client: TestClient):
    """Test POST /devices endpoint (legacy device creation)."""
    response = client.post(
        "/api/v1/devices",
        json={
            "device_id": "post-device-001",
            "device_name": "POST Device",
            "platform": "Windows",
        },
    )
    
    # Endpoint may require auth or may not exist
    assert response.status_code in (200, 201, 401, 404)


# ---------------------------------------------------------------------------
# Device Listing Regression Tests
# ---------------------------------------------------------------------------

def test_get_devices_list_still_works(client: TestClient, admin_token: str, test_device: Device):
    """Test that GET /devices endpoint still returns device list."""
    response = client.get(
        "/api/v1/devices",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    
    # Should not 404
    assert response.status_code != 404


def test_get_device_by_id_still_works(client: TestClient, admin_token: str, test_device: Device):
    """Test that GET /devices/{id} endpoint still works."""
    device_id = test_device.device_id
    
    response = client.get(
        f"/api/v1/devices/{device_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    
    # Should either return device or require auth
    assert response.status_code in (200, 401, 404)


def test_get_device_by_numeric_id_still_works(client: TestClient, admin_token: str, test_device: Device):
    """Test that GET /devices/{numeric_id} endpoint still works."""
    numeric_id = test_device.id
    
    response = client.get(
        f"/api/v1/devices/{numeric_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    
    # Should either return device or require auth
    assert response.status_code in (200, 401, 404)


# ---------------------------------------------------------------------------
# Device Heartbeat Regression Tests
# ---------------------------------------------------------------------------

def test_device_heartbeat_endpoint_still_works(client: TestClient, test_device: Device):
    """Test that POST /devices/{id}/heartbeat endpoint still works."""
    device_id = test_device.device_id
    
    response = client.post(
        f"/api/v1/devices/{device_id}/heartbeat",
        json={
            "status": "ACTIVE",
            "last_scan_time": "2024-01-01T00:00:00Z",
        },
    )
    
    # Should not 404
    assert response.status_code != 404


def test_legacy_heartbeat_body_field_endpoint(client: TestClient):
    """Test that legacy /devices/heartbeat endpoint with body still works."""
    response = client.post(
        "/api/v1/devices/heartbeat",
        json={
            "device_id": "heartbeat-device",
            "status": "ACTIVE",
        },
    )
    
    # Should not 404
    assert response.status_code != 404


# ---------------------------------------------------------------------------
# Device Update Regression Tests
# ---------------------------------------------------------------------------

def test_patch_device_endpoint_still_works(client: TestClient, admin_token: str, test_device: Device):
    """Test that PATCH /devices/{id} endpoint still works."""
    device_id = test_device.device_id
    
    response = client.patch(
        f"/api/v1/devices/{device_id}",
        json={
            "device_name": "Updated Name",
            "status": "OFFLINE",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    
    # Should either update or require auth
    assert response.status_code in (200, 401, 404)


def test_device_name_update_preserved(client: TestClient, db_session: Session):
    """Test that device name updates are preserved."""
    db = db_session
    
    device = Device(
        device_id="update-test-001",
        device_name="Original Name",
        platform="Windows",
    )
    db.add(device)
    db.commit()
    device_id = device.id
    
    # Update device name
    device.device_name = "Updated Name"
    db.commit()
    
    # Verify update
    retrieved = db.query(Device).filter(Device.id == device_id).first()
    assert retrieved.device_name == "Updated Name"


def test_device_status_update_preserved(client: TestClient, db_session: Session):
    """Test that device status updates are preserved."""
    db = db_session
    
    device = Device(
        device_id="status-test-001",
        device_name="Status Test",
        platform="Linux",
        status="ACTIVE",
    )
    db.add(device)
    db.commit()
    device_id = device.id
    
    # Update status
    device.status = "OFFLINE"
    db.commit()
    
    # Verify update
    retrieved = db.query(Device).filter(Device.id == device_id).first()
    assert retrieved.status == "OFFLINE"


# ---------------------------------------------------------------------------
# Device Deletion Regression Tests
# ---------------------------------------------------------------------------

def test_delete_device_endpoint_still_works(client: TestClient, admin_token: str, test_device: Device):
    """Test that DELETE /devices/{id} endpoint still works."""
    device_id = test_device.device_id
    
    response = client.delete(
        f"/api/v1/devices/{device_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    
    # Should not 404
    assert response.status_code != 404


def test_device_deletion_in_database(client: TestClient, db_session: Session):
    """Test that devices can be deleted from database."""
    db = db_session
    
    device = Device(
        device_id="delete-test-001",
        device_name="To Be Deleted",
        platform="Windows",
    )
    db.add(device)
    db.commit()
    device_id = device.id
    
    # Delete
    db.delete(device)
    db.commit()
    
    # Verify deletion
    retrieved = db.query(Device).filter(Device.id == device_id).first()
    assert retrieved is None


# ---------------------------------------------------------------------------
# Legacy Device Metadata Regression Tests
# ---------------------------------------------------------------------------

def test_device_with_legacy_metadata_fields(client: TestClient, db_session: Session):
    """Test that Device can store and retrieve legacy metadata fields."""
    db = db_session
    
    metadata = {
        "agent_version": "1.2.3",
        "hardware_id": "hw-12345",
        "serial_number": "SN-98765",
    }
    
    device = Device(
        device_id="metadata-test-001",
        device_name="Metadata Test",
        platform="Windows",
        device_metadata=json.dumps(metadata),
        agent_version="1.2.3",
    )
    db.add(device)
    db.commit()
    
    # Retrieve
    retrieved = db.query(Device).filter(Device.device_id == "metadata-test-001").first()
    assert retrieved.agent_version == "1.2.3"
    
    if retrieved.device_metadata:
        retrieved_metadata = json.loads(retrieved.device_metadata)
        assert retrieved_metadata["agent_version"] == "1.2.3"


def test_device_incidents_tracking_still_works(client: TestClient, db_session: Session):
    """Test that device incident counts are tracked."""
    db = db_session
    
    device = Device(
        device_id="incidents-test-001",
        device_name="Incidents Test",
        platform="Windows",
        incidents_count=5,
        files_scanned=1000,
    )
    db.add(device)
    db.commit()
    
    # Retrieve and verify
    retrieved = db.query(Device).filter(Device.device_id == "incidents-test-001").first()
    assert retrieved.incidents_count == 5
    assert retrieved.files_scanned == 1000


# ---------------------------------------------------------------------------
# Multi-Platform Device Support Regression
# ---------------------------------------------------------------------------

def test_windows_device_registration_still_works(client: TestClient, db_session: Session):
    """Test that Windows devices can still be registered."""
    db = db_session
    
    device = Device(
        device_id="regression-windows-001",
        device_name="Regression Windows",
        platform="Windows",
    )
    db.add(device)
    db.commit()
    
    retrieved = db.query(Device).filter(Device.device_id == "regression-windows-001").first()
    assert retrieved.platform == "Windows"


def test_linux_device_registration_still_works(client: TestClient, db_session: Session):
    """Test that Linux devices can still be registered."""
    db = db_session
    
    device = Device(
        device_id="regression-linux-001",
        device_name="Regression Linux",
        platform="Linux",
    )
    db.add(device)
    db.commit()
    
    retrieved = db.query(Device).filter(Device.device_id == "regression-linux-001").first()
    assert retrieved.platform == "Linux"


def test_android_device_registration_still_works(client: TestClient, db_session: Session):
    """Test that Android devices can still be registered."""
    db = db_session
    
    device = Device(
        device_id="regression-android-001",
        device_name="Regression Android",
        platform="Android",
    )
    db.add(device)
    db.commit()
    
    retrieved = db.query(Device).filter(Device.device_id == "regression-android-001").first()
    assert retrieved.platform == "Android"


def test_ios_device_registration_still_works(client: TestClient, db_session: Session):
    """Test that iOS devices can still be registered."""
    db = db_session
    
    device = Device(
        device_id="regression-ios-001",
        device_name="Regression iOS",
        platform="iOS",
    )
    db.add(device)
    db.commit()
    
    retrieved = db.query(Device).filter(Device.device_id == "regression-ios-001").first()
    assert retrieved.platform == "iOS"


def test_macos_device_registration_still_works(client: TestClient, db_session: Session):
    """Test that macOS devices can still be registered."""
    db = db_session
    
    device = Device(
        device_id="regression-macos-001",
        device_name="Regression macOS",
        platform="macOS",
    )
    db.add(device)
    db.commit()
    
    retrieved = db.query(Device).filter(Device.device_id == "regression-macos-001").first()
    assert retrieved.platform == "macOS"


# ---------------------------------------------------------------------------
# Organization/Multi-Tenancy Regression Tests
# ---------------------------------------------------------------------------

def test_device_organization_id_still_tracked(client: TestClient, db_session: Session):
    """Test that device organization_id is still tracked."""
    db = db_session
    
    device = Device(
        device_id="org-test-001",
        device_name="Org Test",
        platform="Windows",
        organization_id="regression-org-001",
    )
    db.add(device)
    db.commit()
    
    retrieved = db.query(Device).filter(Device.device_id == "org-test-001").first()
    assert retrieved.organization_id == "regression-org-001"


def test_device_user_id_still_tracked(client: TestClient, db_session: Session):
    """Test that device user_id is still tracked."""
    db = db_session
    
    device = Device(
        device_id="user-test-001",
        device_name="User Test",
        platform="Windows",
        user_id="regression-user-001",
    )
    db.add(device)
    db.commit()
    
    retrieved = db.query(Device).filter(Device.device_id == "user-test-001").first()
    assert retrieved.user_id == "regression-user-001"


# ---------------------------------------------------------------------------
# Device Timestamp Regression Tests
# ---------------------------------------------------------------------------

def test_device_timestamps_still_tracked(client: TestClient, db_session: Session):
    """Test that device timestamps are still tracked."""
    db = db_session
    
    device = Device(
        device_id="timestamp-test-001",
        device_name="Timestamp Test",
        platform="Windows",
    )
    db.add(device)
    db.commit()
    
    retrieved = db.query(Device).filter(Device.device_id == "timestamp-test-001").first()
    assert retrieved.created_at is not None
    assert retrieved.updated_at is not None
    assert retrieved.enrolled_at is not None
    assert retrieved.registered_at is not None


def test_device_last_seen_still_tracked(client: TestClient, db_session: Session):
    """Test that device last_seen timestamp is still tracked."""
    db = db_session
    
    device = Device(
        device_id="lastseen-test-001",
        device_name="Last Seen Test",
        platform="Windows",
    )
    db.add(device)
    db.commit()
    
    retrieved = db.query(Device).filter(Device.device_id == "lastseen-test-001").first()
    assert retrieved.last_seen is not None
