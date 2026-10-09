import pytest
from fastapi.testclient import TestClient
from main import app
from database import init_db

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    init_db()

@pytest.fixture
def auth_headers():
    login_resp = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "dataghost123"},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

def test_create_easy_enrollment_endpoint(auth_headers):
    """Verify /api/devices/enrollment/create-easy endpoint generates a URL-based enrollment QR payload."""
    response = client.post(
        "/api/devices/enrollment/create-easy",
        json={"platform": "Android"},
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert "raw_token" in data
    assert "enrollment_code" in data
    assert data["enrollment_code"].startswith("DG-")
    assert "qr_data" in data
    assert data["platform"] == "Android"
    
    # QR data should be a direct web URL to /enroll/{code}
    assert "/enroll/" in data["qr_data"]
    assert data["enrollment_code"] in data["qr_data"]
    assert "server_url" in data

def test_register_device_via_easy_enrollment_code(auth_headers):
    """Verify an Android or Desktop device can register using the human-readable DG-XXXX-XXXX code."""
    # 1. Generate easy enrollment code
    create_resp = client.post(
        "/api/devices/enrollment/create-easy",
        json={"platform": "Android"},
        headers=auth_headers
    )
    assert create_resp.status_code == 200
    code = create_resp.json()["enrollment_code"]

    # 2. Check initial status is PENDING
    status_resp = client.get(f"/api/devices/enrollment/status/{code}")
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "PENDING"

    # 3. Register device using the code
    reg_resp = client.post(
        "/api/devices/enrollment/register",
        json={
            "enrollment_code": code,
            "device_name": "Test Easy Android Device",
            "platform": "Android",
            "os_name": "Android",
            "os_version": "Android 14 (API 34)",
            "architecture": "arm64-v8a",
            "hostname": "test-phone",
            "ip_address": "192.168.1.100",
            "agent_version": "1.0.0",
        }
    )
    assert reg_resp.status_code == 200
    reg_data = reg_resp.json()
    assert "device_id" in reg_data
    assert "auth_token" in reg_data
    assert reg_data["device_name"] == "Test Easy Android Device"

    # 4. Status should now be USED
    status_resp2 = client.get(f"/api/devices/enrollment/status/{code}")
    assert status_resp2.status_code == 200
    assert status_resp2.json()["status"] == "USED"

def test_download_dataghost_agent_apk():
    """Verify /dataghost-agent.apk serves the built Android APK file."""
    resp = client.get("/dataghost-agent.apk")
    assert resp.status_code == 200
    assert resp.headers.get("content-type") == "application/vnd.android.package-archive"
    assert len(resp.content) > 100000  # valid APK size (> 100KB)

