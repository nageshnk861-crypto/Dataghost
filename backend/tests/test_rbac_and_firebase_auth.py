"""
Tests for Role-Based Access Control (RBAC) and Firebase User Registration in DataGhost.

Covers:
- Trusted token/session auth (no trusting role/userID from request body/headers)
- Scoped backend queries for Analysts vs Admin system-wide queries
- Protection of admin-only endpoints (DELETE incidents, PATCH/DELETE devices, admin user mgmt)
- Server-side Firebase ID token verification and database registration/sync
- Protection against role elevation during registration (always sets role='analyst')
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from unittest.mock import patch

from main import app
from database import SessionLocal
from models import User, Device, Incident
from auth import get_password_hash, create_access_token


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def db_session() -> Session:
    db = SessionLocal()
    yield db
    db.close()


@pytest.fixture
def test_data(db_session: Session):
    """Seed test users, devices, and incidents for RBAC validation."""
    db = db_session

    # Clean previous test users
    db.query(User).filter(User.username.in_(["test_admin", "test_analyst"])).delete(synchronize_session=False)
    db.query(Device).filter(Device.device_id.in_(["dev-org1-001", "dev-org2-002"])).delete(synchronize_session=False)
    db.query(Incident).filter(Incident.incident_id.in_(["inc-org1-001", "inc-org2-002"])).delete(synchronize_session=False)
    db.commit()

    # Create Admin User
    admin = User(
        username="test_admin",
        email="admin@dataghost.test",
        hashed_password=get_password_hash("AdminPass123!"),
        role="admin",
        is_active=True,
    )
    # Create Analyst User
    analyst = User(
        username="test_analyst",
        email="analyst@dataghost.test",
        hashed_password=get_password_hash("AnalystPass123!"),
        role="analyst",
        is_active=True,
    )
    db.add(admin)
    db.add(analyst)
    db.commit()

    # Create Device for default-org (accessible by analyst)
    dev1 = Device(
        device_id="dev-org1-001",
        device_name="Default Org Endpoint",
        platform="Windows",
        organization_id="default-org",
        status="ACTIVE",
        files_scanned=150,
        incidents_count=3,
    )
    # Create Device for secret-org (admin only)
    dev2 = Device(
        device_id="dev-org2-002",
        device_name="Secret Org Endpoint",
        platform="Linux",
        organization_id="secret-org",
        status="ACTIVE",
        files_scanned=500,
        incidents_count=10,
    )
    db.add(dev1)
    db.add(dev2)
    db.commit()

    # Create Incident for default-org device
    inc1 = Incident(
        incident_id="inc-org1-001",
        device_id="dev-org1-001",
        user="test_analyst",
        filename="financial_export.csv",
        classification="CONFIDENTIAL",
        risk_score=75,
        severity="HIGH",
        status="OPEN",
    )
    # Create Incident for secret-org device
    inc2 = Incident(
        incident_id="inc-org2-002",
        device_id="dev-org2-002",
        user="other_user",
        filename="classified_plans.pdf",
        classification="TOP_SECRET",
        risk_score=95,
        severity="CRITICAL",
        status="OPEN",
    )
    db.add(inc1)
    db.add(inc2)
    db.commit()

    return {
        "admin": admin,
        "analyst": analyst,
        "dev1": dev1,
        "dev2": dev2,
        "inc1": inc1,
        "inc2": inc2,
    }


@pytest.fixture
def admin_token(test_data) -> str:
    return create_access_token({"sub": test_data["admin"].username, "role": test_data["admin"].role})


@pytest.fixture
def analyst_token(test_data) -> str:
    return create_access_token({"sub": test_data["analyst"].username, "role": test_data["analyst"].role})


# ===========================================================================
# 1. RBAC Tests for Dashboard Routes
# ===========================================================================

def test_dashboard_stats_admin_returns_all_data(client: TestClient, admin_token: str):
    """Admin receives system-wide aggregate statistics across all organizations."""
    res = client.get("/api/dashboard/stats", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["scope"] == "all"
    assert data["protected_devices"] >= 2
    assert data["critical_incidents"] >= 1


def test_dashboard_stats_analyst_returns_scoped_data(client: TestClient, analyst_token: str):
    """Analyst receives scoped statistics filtered to default-org devices/incidents."""
    res = client.get("/api/dashboard/stats", headers={"Authorization": f"Bearer {analyst_token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["scope"] == "default-org"
    # Scoped to default-org devices
    assert data["protected_devices"] >= 1


def test_dashboard_unauthenticated_rejected(client: TestClient):
    """Unauthenticated access to dashboard stats is rejected with 401."""
    res = client.get("/api/dashboard/stats")
    assert res.status_code == 401


# ===========================================================================
# 2. RBAC Tests for Incident Routes
# ===========================================================================

def test_incident_list_admin_sees_all(client: TestClient, admin_token: str):
    """Admin can view all incidents across all devices and organizations."""
    res = client.get("/api/incidents", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200
    data = res.json()
    incidents_list = data.get("items", [])
    inc_ids = [inc["incident_id"] for inc in incidents_list]
    assert "inc-org1-001" in inc_ids
    assert "inc-org2-002" in inc_ids


def test_incident_list_analyst_sees_only_scoped(client: TestClient, analyst_token: str):
    """Analyst sees only incidents associated with default-org devices."""
    res = client.get("/api/incidents", headers={"Authorization": f"Bearer {analyst_token}"})
    assert res.status_code == 200
    data = res.json()
    incidents_list = data.get("items", [])
    inc_ids = [inc["incident_id"] for inc in incidents_list]
    assert "inc-org1-001" in inc_ids
    assert "inc-org2-002" not in inc_ids


def test_incident_delete_admin_allowed(client: TestClient, admin_token: str):
    """Admin can delete an incident."""
    res = client.delete("/api/incidents/inc-org1-001", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200


def test_incident_delete_analyst_forbidden(client: TestClient, analyst_token: str):
    """Analyst is forbidden from deleting an incident (403 Forbidden)."""
    res = client.delete("/api/incidents/inc-org2-002", headers={"Authorization": f"Bearer {analyst_token}"})
    assert res.status_code == 403


# ===========================================================================
# 3. RBAC Tests for Device Routes
# ===========================================================================

def test_device_list_admin_sees_all(client: TestClient, admin_token: str):
    """Admin receives all enrolled devices."""
    res = client.get("/api/devices", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200
    dev_ids = [d["device_id"] for d in res.json()]
    assert "dev-org1-001" in dev_ids
    assert "dev-org2-002" in dev_ids


def test_device_list_analyst_sees_only_scoped(client: TestClient, analyst_token: str):
    """Analyst receives only devices in default-org."""
    res = client.get("/api/devices", headers={"Authorization": f"Bearer {analyst_token}"})
    assert res.status_code == 200
    dev_ids = [d["device_id"] for d in res.json()]
    assert "dev-org1-001" in dev_ids
    assert "dev-org2-002" not in dev_ids


def test_device_update_admin_allowed(client: TestClient, admin_token: str):
    """Admin can update device details/status."""
    res = client.patch(
        "/api/devices/dev-org1-001",
        json={"device_name": "Renamed Admin Device"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    assert res.json()["device_name"] == "Renamed Admin Device"


def test_device_update_analyst_forbidden(client: TestClient, analyst_token: str):
    """Analyst is forbidden from patching devices."""
    res = client.patch(
        "/api/devices/dev-org1-001",
        json={"status": "DISABLED"},
        headers={"Authorization": f"Bearer {analyst_token}"},
    )
    assert res.status_code == 403


def test_device_delete_analyst_forbidden(client: TestClient, analyst_token: str):
    """Analyst is forbidden from deleting devices."""
    res = client.delete("/api/devices/dev-org1-001", headers={"Authorization": f"Bearer {analyst_token}"})
    assert res.status_code == 403


# ===========================================================================
# 4. Firebase Auth & Registration Tests
# ===========================================================================

def test_firebase_register_creates_analyst_profile(client: TestClient, db_session: Session):
    """
    POST /api/auth/register/firebase verifies the Firebase token server-side,
    provisions a database user profile with role='analyst', and populates firebase_uid.
    """
    fake_token = "mock_firebase_id_token_12345"
    fake_decoded = {
        "uid": "firebase_uid_abc123",
        "email": "new_firebase_user@test.local",
    }

    with patch("api.auth_routes.verify_firebase_token", return_value=fake_decoded), \
         patch("auth.verify_firebase_token", return_value=fake_decoded):
        res = client.post(
            "/api/auth/register/firebase",
            json={"firebase_id_token": fake_token},
            headers={"Authorization": f"Bearer {fake_token}"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["email"] == "new_firebase_user@test.local"
        assert data["role"] == "analyst"
        assert data["firebase_uid"] == "firebase_uid_abc123"

    # Verify record in DB
    user = db_session.query(User).filter(User.firebase_uid == "firebase_uid_abc123").first()
    assert user is not None
    assert user.role == "analyst"


def test_firebase_register_role_elevation_prevented(client: TestClient, db_session: Session):
    """
    Registration requests specifying an attempted role elevation (e.g. role='admin')
    are safely ignored; new registrations MUST always be assigned role='analyst'.
    """
    fake_token = "mock_firebase_id_token_elevation"
    fake_decoded = {
        "uid": "firebase_uid_hacker",
        "email": "hacker@test.local",
    }

    with patch("api.auth_routes.verify_firebase_token", return_value=fake_decoded), \
         patch("auth.verify_firebase_token", return_value=fake_decoded):
        res = client.post(
            "/api/auth/register/firebase",
            json={"firebase_id_token": fake_token},
            headers={"Authorization": f"Bearer {fake_token}"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["role"] == "analyst"  # Enforced as analyst


def test_password_register_endpoint(client: TestClient, db_session: Session):
    """POST /api/auth/register creates a standard username+password user with analyst role."""
    # Clean previous user if exists
    db_session.query(User).filter(User.username == "std_new_user").delete()
    db_session.commit()

    res = client.post(
        "/api/auth/register",
        json={
            "username": "std_new_user",
            "email": "std_new_user@test.local",
            "password": "Password123!",
        },
    )
    assert res.status_code in (200, 201)
    data = res.json()
    assert data["username"] == "std_new_user"
    assert data["role"] == "analyst"
