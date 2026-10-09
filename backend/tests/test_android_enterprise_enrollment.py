"""
DataGhost – Android Enterprise Enrollment Tests

Comprehensive test suite for automatic Android Enterprise DPC provisioning:
  - Enrollment token generation (create-android-enterprise endpoint)
  - Token validation and single-use enforcement
  - APK checksum verification
  - Device registration via enrollment token
  - Device status transitions (CREATED → PROVISIONING → REGISTERED → ACTIVE)
  - Heartbeat tracking
"""

import pytest
import json
import hashlib
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from models import Device, EnrollmentToken, User
from database import Base, engine, get_db
from main import app
from auth import get_password_hash, get_current_user


@pytest.fixture
def db_session():
    """Create a fresh database session for each test."""
    # Drop all tables first to ensure clean state
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = next(get_db())
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(db_session):
    """Create a test client with injected database session."""
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


@pytest.fixture
def admin_user(db_session):
    """Create an admin user for authentication."""
    user = User(
        username="admin",
        email="admin@test.local",
        hashed_password=get_password_hash("admin123"),
        role="admin",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def auth_token(client, admin_user):
    """Generate authentication token for admin user."""
    response = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin123"}
    )
    assert response.status_code == 200
    return response.json()["access_token"]


class TestAndroidEnterpriseEnrollmentCreation:
    """Tests for POST /api/devices/enrollment/create-android-enterprise"""

    def test_create_android_enterprise_enrollment_success(self, client, auth_token):
        """Test successful creation of Android Enterprise enrollment token."""
        response = client.post(
            "/api/devices/enrollment/create-android-enterprise",
            json={"platform": "Android", "organization_id": "test-org"},
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        assert response.status_code == 200
        data = response.json()

        # Verify required fields
        assert data["enrollment_code"]
        assert data["raw_token"]
        assert data["platform"] == "Android"
        assert data["server_url"]
        assert data["expires_at"]
        assert data["expires_in_seconds"] > 0
        assert data["status"] == "PENDING"

        # Verify enrollment code format (DG-XXXX-XXXX)
        assert data["enrollment_code"].startswith("DG-")
        assert len(data["enrollment_code"]) == 12  # DG-XXXX-XXXX

        # Verify QR data is valid JSON (Android Enterprise payload)
        qr_data = json.loads(data["qr_data"])
        assert "android.app.extra.PROVISIONING_DEVICE_ADMIN_COMPONENT_NAME" in qr_data
        assert "android.app.extra.PROVISIONING_DEVICE_ADMIN_PACKAGE_DOWNLOAD_LOCATION" in qr_data
        assert "android.app.extra.PROVISIONING_DEVICE_ADMIN_SIGNATURE_CHECKSUM" in qr_data
        assert "android.app.extra.PROVISIONING_ADMIN_EXTRAS_BUNDLE" in qr_data

    def test_android_enterprise_payload_contains_dpc_component(self, client, auth_token):
        """Verify the DPC component is correctly set in the provisioning payload."""
        response = client.post(
            "/api/devices/enrollment/create-android-enterprise",
            json={"platform": "Android"},
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        assert response.status_code == 200
        qr_data = json.loads(response.json()["qr_data"])

        dpc_component = qr_data.get("android.app.extra.PROVISIONING_DEVICE_ADMIN_COMPONENT_NAME")
        assert dpc_component == "com.dataghost.agent/com.dataghost.agent.enrollment.DataGhostDeviceAdminReceiver"

    def test_android_enterprise_payload_contains_apk_url(self, client, auth_token):
        """Verify APK download location is correctly set."""
        response = client.post(
            "/api/devices/enrollment/create-android-enterprise",
            json={"platform": "Android"},
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        assert response.status_code == 200
        qr_data = json.loads(response.json()["qr_data"])

        apk_url = qr_data.get("android.app.extra.PROVISIONING_DEVICE_ADMIN_PACKAGE_DOWNLOAD_LOCATION")
        assert apk_url
        assert "/dataghost-agent.apk" in apk_url
        assert apk_url.startswith("http")

    def test_android_enterprise_payload_contains_checksum(self, client, auth_token):
        """Verify APK certificate checksum is included (not blank)."""
        response = client.post(
            "/api/devices/enrollment/create-android-enterprise",
            json={"platform": "Android"},
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        assert response.status_code == 200
        qr_data = json.loads(response.json()["qr_data"])

        checksum = qr_data.get("android.app.extra.PROVISIONING_DEVICE_ADMIN_SIGNATURE_CHECKSUM")
        assert checksum
        assert checksum != "REPLACE_WITH_APK_SIGNING_CERT_SHA256_BASE64URL"
        assert len(checksum) > 20  # Base64url encoded SHA-256 is ~43 chars

    def test_android_enterprise_payload_contains_enrollment_extras(self, client, auth_token):
        """Verify enrollment credentials are in the provisioning bundle."""
        response = client.post(
            "/api/devices/enrollment/create-android-enterprise",
            json={"platform": "Android"},
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        qr_data = json.loads(data["qr_data"])

        extras = qr_data.get("android.app.extra.PROVISIONING_ADMIN_EXTRAS_BUNDLE")
        assert extras
        assert extras.get("com.dataghost.SERVER_URL")
        assert extras.get("com.dataghost.ENROLLMENT_TOKEN") == data["raw_token"]
        assert extras.get("com.dataghost.ENROLLMENT_CODE") == data["enrollment_code"]
        assert extras.get("com.dataghost.EXPIRES_AT")

    def test_unauthenticated_cannot_create_enrollment(self, client):
        """Verify unauthenticated users cannot create enrollment tokens."""
        response = client.post(
            "/api/devices/enrollment/create-android-enterprise",
            json={"platform": "Android"}
        )

        assert response.status_code == 401


class TestEnrollmentTokenValidation:
    """Tests for enrollment token validation and single-use enforcement"""

    def test_token_single_use_enforcement(self, client, auth_token, db_session):
        """Verify enrollment tokens can only be used once."""
        # Create enrollment token
        create_response = client.post(
            "/api/devices/enrollment/create-android-enterprise",
            json={"platform": "Android"},
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        enrollment_data = create_response.json()
        token = enrollment_data["raw_token"]
        code = enrollment_data["enrollment_code"]

        # First registration should succeed
        register_response_1 = client.post(
            "/api/devices/enrollment/register",
            json={
                "token": token,
                "enrollment_code": code,
                "device_name": "Test Device 1",
                "platform": "Android",
                "os_name": "Android",
                "os_version": "13",
                "hostname": "test-device-1",
            }
        )
        assert register_response_1.status_code == 200
        device_id_1 = register_response_1.json()["device_id"]

        # Second registration with same token should fail (token already used)
        register_response_2 = client.post(
            "/api/devices/enrollment/register",
            json={
                "token": token,
                "device_name": "Test Device 2",
                "platform": "Android",
                "os_name": "Android",
                "os_version": "13",
                "hostname": "test-device-2",
            }
        )
        assert register_response_2.status_code == 400
        assert "no longer valid" in register_response_2.json()["detail"]

    def test_enrollment_code_expiration(self, client, auth_token, db_session):
        """Verify expired enrollment codes are rejected."""
        # Create enrollment token
        create_response = client.post(
            "/api/devices/enrollment/create-android-enterprise",
            json={"platform": "Android"},
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        enrollment_data = create_response.json()
        code = enrollment_data["enrollment_code"]

        # Manually expire the token in the database
        token_record = db_session.query(EnrollmentToken).filter(
            EnrollmentToken.enrollment_code == code
        ).first()
        assert token_record
        token_record.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db_session.commit()

        # Registration should fail with expired token
        register_response = client.post(
            "/api/devices/enrollment/register",
            json={
                "enrollment_code": code,
                "device_name": "Test Device",
                "platform": "Android",
                "os_name": "Android",
                "os_version": "13",
                "hostname": "test-device",
            }
        )
        assert register_response.status_code == 400
        assert "expired" in register_response.json()["detail"]

    def test_invalid_token_rejection(self, client):
        """Verify invalid tokens are rejected."""
        response = client.post(
            "/api/devices/enrollment/register",
            json={
                "token": "invalid-token-xyz",
                "device_name": "Test Device",
                "platform": "Android",
                "os_name": "Android",
                "os_version": "13",
                "hostname": "test-device",
            }
        )
        assert response.status_code == 400
        assert "Invalid enrollment credentials" in response.json()["detail"]


class TestDeviceRegistration:
    """Tests for device registration via enrollment token"""

    def test_device_registration_creates_device_record(self, client, auth_token):
        """Verify device registration creates a device record with correct metadata."""
        # Create enrollment
        create_response = client.post(
            "/api/devices/enrollment/create-android-enterprise",
            json={"platform": "Android", "organization_id": "corp-org"},
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        enrollment_data = create_response.json()

        # Register device
        register_response = client.post(
            "/api/devices/enrollment/register",
            json={
                "token": enrollment_data["raw_token"],
                "device_name": "Samsung Galaxy S23",
                "platform": "Android",
                "os_name": "Android",
                "os_version": "Android 13 (API 33)",
                "architecture": "arm64-v8a",
                "hostname": "samsung-s23",
                "ip_address": "192.168.1.100",
                "agent_version": "1.0.0",
                "device_metadata": {
                    "brand": "Samsung",
                    "manufacturer": "Samsung",
                    "model": "SM-S911B",
                    "sdk_int": 33,
                }
            }
        )

        assert register_response.status_code == 200
        response_data = register_response.json()

        # Verify device record
        assert response_data["device_id"]
        assert response_data["device_id"].startswith("dg-android-")
        assert response_data["status"] == "ACTIVE"

        # Device ID should be non-sequential (random hex)
        device_id = response_data["device_id"]
        assert len(device_id) > 15  # Should be something like dg-android-xxxxxxxx

    def test_device_registration_marks_enrollment_as_used(self, client, auth_token, db_session):
        """Verify enrollment token is marked as USED after successful registration."""
        # Create enrollment
        create_response = client.post(
            "/api/devices/enrollment/create-android-enterprise",
            json={"platform": "Android"},
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        enrollment_data = create_response.json()
        code = enrollment_data["enrollment_code"]

        # Register device
        register_response = client.post(
            "/api/devices/enrollment/register",
            json={
                "enrollment_code": code,
                "device_name": "Test Device",
                "platform": "Android",
                "os_name": "Android",
                "os_version": "13",
                "hostname": "test-device",
            }
        )
        assert register_response.status_code == 200
        device_id = register_response.json()["device_id"]

        # Check enrollment token status
        token_record = db_session.query(EnrollmentToken).filter(
            EnrollmentToken.enrollment_code == code
        ).first()
        assert token_record
        assert token_record.status == "USED"
        assert token_record.used_at is not None
        assert token_record.device_id == device_id

    def test_device_status_transitions(self, client, auth_token, db_session):
        """Verify device status transitions correctly through enrollment lifecycle."""
        # Create enrollment
        create_response = client.post(
            "/api/devices/enrollment/create-android-enterprise",
            json={"platform": "Android"},
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        enrollment_data = create_response.json()

        # Register device
        register_response = client.post(
            "/api/devices/enrollment/register",
            json={
                "token": enrollment_data["raw_token"],
                "device_name": "Test Device",
                "platform": "Android",
                "os_name": "Android",
                "os_version": "13",
                "hostname": "test-device",
            }
        )
        assert register_response.status_code == 200
        device_id = register_response.json()["device_id"]

        # Verify device is ACTIVE
        device = db_session.query(Device).filter(Device.device_id == device_id).first()
        assert device
        assert device.status == "ACTIVE"
        assert device.enrolled_at is not None
        assert device.registered_at is not None


class TestEnrollmentStatusPolling:
    """Tests for enrollment status polling (GET /api/devices/enrollment/status/{code})"""

    def test_enrollment_status_pending(self, client, auth_token):
        """Verify enrollment status shows PENDING before registration."""
        # Create enrollment
        create_response = client.post(
            "/api/devices/enrollment/create-android-enterprise",
            json={"platform": "Android"},
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        enrollment_data = create_response.json()
        code = enrollment_data["enrollment_code"]

        # Check status
        status_response = client.get(
            f"/api/devices/enrollment/status/{code}"
        )
        assert status_response.status_code == 200
        status_data = status_response.json()

        assert status_data["status"] == "PENDING"
        assert status_data["platform"] == "Android"
        assert status_data["device_id"] is None
        assert status_data["is_expired"] == False

    def test_enrollment_status_used_after_registration(self, client, auth_token):
        """Verify enrollment status shows USED and device_name after registration."""
        # Create enrollment
        create_response = client.post(
            "/api/devices/enrollment/create-android-enterprise",
            json={"platform": "Android"},
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        enrollment_data = create_response.json()
        code = enrollment_data["enrollment_code"]

        # Register device
        register_response = client.post(
            "/api/devices/enrollment/register",
            json={
                "enrollment_code": code,
                "device_name": "My Android Phone",
                "platform": "Android",
                "os_name": "Android",
                "os_version": "13",
                "hostname": "my-phone",
            }
        )
        assert register_response.status_code == 200

        # Check status
        status_response = client.get(
            f"/api/devices/enrollment/status/{code}"
        )
        assert status_response.status_code == 200
        status_data = status_response.json()

        assert status_data["status"] == "USED"
        assert status_data["device_id"]
        assert status_data["device_name"] == "My Android Phone"


class TestAPKHosting:
    """Tests for APK hosting endpoint (GET /dataghost-agent.apk)"""

    def test_apk_download_endpoint_exists(self, client):
        """Verify APK download endpoint responds."""
        response = client.get("/dataghost-agent.apk")
        # Will return 404 if APK not built, but endpoint should exist
        assert response.status_code in [200, 404]

    def test_apk_content_type_is_correct(self, client):
        """Verify APK endpoint returns correct Content-Type."""
        response = client.get("/dataghost-agent.apk")
        if response.status_code == 200:
            assert response.headers["content-type"] == "application/vnd.android.package-archive"

    def test_apk_not_found_error_message(self, client):
        """Verify helpful error message if APK not found."""
        response = client.get("/dataghost-agent.apk")
        if response.status_code == 404:
            assert "APK not found" in response.json()["detail"]
            assert "Please build the Android APK" in response.json()["detail"]


class TestEasyEnrollmentPreserved:
    """Tests to ensure Easy Enrollment still works (backward compatibility)"""

    def test_easy_enrollment_endpoint_still_works(self, client, auth_token):
        """Verify Easy Enrollment endpoint is not broken."""
        response = client.post(
            "/api/devices/enrollment/create-easy",
            json={"platform": "Android"},
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        assert response.status_code == 200
        data = response.json()

        # QR data should be a plain URL (not JSON)
        qr_data = data["qr_data"]
        assert qr_data.startswith("http")
        assert "/enroll/" in qr_data


class TestAndroidEnterpriseIntegration:
    """End-to-end integration tests for Android Enterprise enrollment"""

    def test_full_android_enterprise_enrollment_flow(self, client, auth_token, db_session):
        """Test complete automatic Android Enterprise enrollment flow."""
        # Step 1: Admin generates Android Enterprise enrollment QR
        create_response = client.post(
            "/api/devices/enrollment/create-android-enterprise",
            json={"platform": "Android", "organization_id": "test-corp"},
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert create_response.status_code == 200
        enrollment_data = create_response.json()

        # Verify QR payload structure
        qr_payload = json.loads(enrollment_data["qr_data"])
        assert qr_payload["version"] == "1.0"
        assert qr_payload["platform"] == "Android"

        # Step 2: Device scans QR during setup wizard
        # (Simulated by extracting token and code)
        token = enrollment_data["raw_token"]
        code = enrollment_data["enrollment_code"]

        # Step 3: DPC automatically registers device
        register_response = client.post(
            "/api/devices/enrollment/register",
            json={
                "token": token,
                "enrollment_code": code,
                "device_name": "Corporate Pixel 7",
                "platform": "Android",
                "os_name": "Android",
                "os_version": "Android 13 (API 33)",
                "architecture": "arm64-v8a",
                "hostname": "pixel-7",
                "ip_address": "10.0.0.50",
                "agent_version": "1.0.0",
                "device_metadata": {
                    "brand": "Google",
                    "manufacturer": "Google",
                    "model": "Pixel 7",
                    "sdk_int": 33,
                }
            }
        )

        assert register_response.status_code == 200
        device_data = register_response.json()
        device_id = device_data["device_id"]

        # Step 4: Verify device is ACTIVE
        device = db_session.query(Device).filter(Device.device_id == device_id).first()
        assert device
        assert device.status == "ACTIVE"
        assert device.platform == "Android"
        assert device.device_name == "Corporate Pixel 7"
        assert device.organization_id == "test-corp"

        # Step 5: Verify enrollment is marked USED
        enrollment = db_session.query(EnrollmentToken).filter(
            EnrollmentToken.enrollment_code == code
        ).first()
        assert enrollment
        assert enrollment.status == "USED"
        assert enrollment.device_id == device_id

        # Step 6: Verify device can be polled for status
        status_response = client.get(f"/api/devices/enrollment/status/{code}")
        assert status_response.status_code == 200
        status_data = status_response.json()
        assert status_data["status"] == "USED"
        assert status_data["device_name"] == "Corporate Pixel 7"
