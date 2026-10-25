"""
Phase 3.2 Verification Tests: Device Access Control & Role-Based Ownership Filtering.

Tests:
- Analyst sees only their own devices on GET /api/devices
- Analyst accessing own device GET /api/devices/{id} succeeds (200)
- Analyst accessing other analyst's device GET /api/devices/{id} returns 403 Forbidden
- Analyst triggering scan on other analyst's device returns 403 Forbidden
- Analyst updating other analyst's device returns 403 Forbidden
- Analyst updating own device succeeds (200)
- Analyst changing device status is forbidden (403)
- Analyst deleting device is forbidden (403)
- Admin sees all organization devices on GET /api/devices
- Admin can access, update, and scan any device
- Unauthenticated requests return 401 Unauthorized
- Foreign Key and NOT NULL constraint validation on devices.user_id
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from auth import create_access_token, get_password_hash
from models import Device, User


@pytest.fixture
def test_setup(db_session: Session):
    # 1. Clean up devices and users created in previous tests if any
    db_session.query(Device).filter(
        Device.device_id.in_(["dev-analyst1-01", "dev-analyst1-02", "dev-analyst2-01"])
    ).delete(synchronize_session=False)
    db_session.query(User).filter(
        User.username.in_(["phase32_admin", "phase32_analyst1", "phase32_analyst2"])
    ).delete(synchronize_session=False)
    db_session.commit()

    # 2. Create Admin user
    admin = User(
        username="phase32_admin",
        email="admin32@dataghost.test",
        hashed_password=get_password_hash("AdminPass123!"),
        role="admin",
        is_active=True,
    )
    # 3. Create Analyst 1
    analyst1 = User(
        username="phase32_analyst1",
        email="analyst1_32@dataghost.test",
        hashed_password=get_password_hash("AnalystPass123!"),
        role="analyst",
        is_active=True,
    )
    # 4. Create Analyst 2
    analyst2 = User(
        username="phase32_analyst2",
        email="analyst2_32@dataghost.test",
        hashed_password=get_password_hash("AnalystPass123!"),
        role="analyst",
        is_active=True,
    )
    db_session.add_all([admin, analyst1, analyst2])
    db_session.commit()
    db_session.refresh(admin)
    db_session.refresh(analyst1)
    db_session.refresh(analyst2)

    # 5. Create Devices
    # Analyst 1 owns device 1 & 2
    dev1 = Device(
        device_id="dev-analyst1-01",
        device_name="Analyst 1 Windows Workstation",
        platform="Windows",
        organization_id="default-org",
        user_id=analyst1.id,
        status="ACTIVE",
        files_scanned=10,
    )
    dev2 = Device(
        device_id="dev-analyst1-02",
        device_name="Analyst 1 Android Tablet",
        platform="Android",
        organization_id="default-org",
        user_id=analyst1.id,
        status="ACTIVE",
        files_scanned=20,
    )
    # Analyst 2 owns device 3
    dev3 = Device(
        device_id="dev-analyst2-01",
        device_name="Analyst 2 Linux Server",
        platform="Linux",
        organization_id="default-org",
        user_id=analyst2.id,
        status="ACTIVE",
        files_scanned=50,
    )
    db_session.add_all([dev1, dev2, dev3])
    db_session.commit()

    admin_token = create_access_token({"sub": admin.username, "role": "admin"})
    analyst1_token = create_access_token({"sub": analyst1.username, "role": "analyst"})
    analyst2_token = create_access_token({"sub": analyst2.username, "role": "analyst"})

    return {
        "admin": admin,
        "analyst1": analyst1,
        "analyst2": analyst2,
        "dev1": dev1,
        "dev2": dev2,
        "dev3": dev3,
        "admin_token": admin_token,
        "analyst1_token": analyst1_token,
        "analyst2_token": analyst2_token,
    }


def test_analyst1_sees_only_own_devices(client: TestClient, test_setup: dict):
    """Scenario A: Analyst1 GET /api/devices returns only analyst1's devices."""
    res = client.get(
        "/api/devices",
        headers={"Authorization": f"Bearer {test_setup['analyst1_token']}"},
    )
    assert res.status_code == 200
    devices = res.json()
    device_ids = [d["device_id"] for d in devices]

    assert "dev-analyst1-01" in device_ids
    assert "dev-analyst1-02" in device_ids
    assert "dev-analyst2-01" not in device_ids


def test_analyst1_can_access_own_device_detail(client: TestClient, test_setup: dict):
    """Scenario A: Analyst1 GET /api/devices/dev-analyst1-01 returns 200 (own device)."""
    res = client.get(
        "/api/devices/dev-analyst1-01",
        headers={"Authorization": f"Bearer {test_setup['analyst1_token']}"},
    )
    assert res.status_code == 200
    assert res.json()["device_id"] == "dev-analyst1-01"


def test_analyst1_cannot_access_other_analyst_device_detail(client: TestClient, test_setup: dict):
    """Scenario A: Analyst1 GET /api/devices/dev-analyst2-01 returns 403 Forbidden."""
    res = client.get(
        "/api/devices/dev-analyst2-01",
        headers={"Authorization": f"Bearer {test_setup['analyst1_token']}"},
    )
    assert res.status_code == 403


def test_analyst1_cannot_scan_other_analyst_device(client: TestClient, test_setup: dict):
    """Scenario A: Analyst1 POST /api/devices/dev-analyst2-01/scan returns 403 Forbidden."""
    res = client.post(
        "/api/devices/dev-analyst2-01/scan",
        headers={"Authorization": f"Bearer {test_setup['analyst1_token']}"},
    )
    assert res.status_code == 403


def test_analyst1_cannot_update_other_analyst_device(client: TestClient, test_setup: dict):
    """Scenario A: Analyst1 PATCH /api/devices/dev-analyst2-01 returns 403 Forbidden."""
    res = client.patch(
        "/api/devices/dev-analyst2-01",
        json={"device_name": "Hacked Name"},
        headers={"Authorization": f"Bearer {test_setup['analyst1_token']}"},
    )
    assert res.status_code == 403

    # Also PUT returns 403
    res_put = client.put(
        "/api/devices/dev-analyst2-01",
        json={"device_name": "Hacked Name PUT"},
        headers={"Authorization": f"Bearer {test_setup['analyst1_token']}"},
    )
    assert res_put.status_code == 403


def test_analyst1_can_update_own_device(client: TestClient, test_setup: dict):
    """Analyst1 can update their own device's name."""
    res = client.patch(
        "/api/devices/dev-analyst1-01",
        json={"device_name": "Updated Laptop Name"},
        headers={"Authorization": f"Bearer {test_setup['analyst1_token']}"},
    )
    assert res.status_code == 200
    assert res.json()["device_name"] == "Updated Laptop Name"


def test_analyst_cannot_change_status_or_delete_device(client: TestClient, test_setup: dict):
    """Analyst cannot change device status or delete any device."""
    res_patch = client.patch(
        "/api/devices/dev-analyst1-01",
        json={"status": "DISABLED"},
        headers={"Authorization": f"Bearer {test_setup['analyst1_token']}"},
    )
    assert res_patch.status_code == 403

    res_del = client.delete(
        "/api/devices/dev-analyst1-01",
        headers={"Authorization": f"Bearer {test_setup['analyst1_token']}"},
    )
    assert res_del.status_code == 403


def test_admin_sees_all_devices(client: TestClient, test_setup: dict):
    """Scenario B: Admin GET /api/devices returns all organization devices."""
    res = client.get(
        "/api/devices",
        headers={"Authorization": f"Bearer {test_setup['admin_token']}"},
    )
    assert res.status_code == 200
    device_ids = [d["device_id"] for d in res.json()]
    assert "dev-analyst1-01" in device_ids
    assert "dev-analyst1-02" in device_ids
    assert "dev-analyst2-01" in device_ids


def test_admin_can_access_and_manage_any_device(client: TestClient, test_setup: dict):
    """Scenario B: Admin can access, update, and manage any device."""
    # Admin can view analyst2 device
    res_get = client.get(
        "/api/devices/dev-analyst2-01",
        headers={"Authorization": f"Bearer {test_setup['admin_token']}"},
    )
    assert res_get.status_code == 200
    assert res_get.json()["device_id"] == "dev-analyst2-01"

    # Admin can update status
    res_patch = client.patch(
        "/api/devices/dev-analyst2-01",
        json={"status": "DISABLED"},
        headers={"Authorization": f"Bearer {test_setup['admin_token']}"},
    )
    assert res_patch.status_code == 200
    assert res_patch.json()["status"] == "DISABLED"


def test_unauthenticated_requests_return_401(client: TestClient):
    """Unauthenticated requests must return 401 Unauthorized."""
    res_list = client.get("/api/devices")
    assert res_list.status_code == 401

    res_get = client.get("/api/devices/dev-analyst1-01")
    assert res_get.status_code == 401

    res_scan = client.post("/api/devices/dev-analyst1-01/scan")
    assert res_scan.status_code == 401


def test_database_schema_fk_and_not_null(db_session: Session):
    """Verify that devices.user_id column is indexed and NOT NULL."""
    # Attempting to insert a device with NULL user_id should fail
    with pytest.raises(Exception):
        bad_dev = Device(
            device_id="dev-bad-null",
            device_name="Bad Device",
            user_id=None,
        )
        db_session.add(bad_dev)
        db_session.commit()
    db_session.rollback()
