"""
Tests for Authentication Routes (/auth/login, /auth/me, role persistence and re-verification).

Covers:
- Login returns valid JWT and database-backed role
- GET /auth/me returns id, email, username, and role
- GET /auth/me rejects invalid or missing token with 401
- Role updates in database are immediately reflected in GET /auth/me
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from main import app
from database import SessionLocal, init_db
from models import User
from auth import get_password_hash, create_access_token


@pytest.fixture
def client() -> TestClient:
    init_db()
    return TestClient(app)


@pytest.fixture
def db_session() -> Session:
    db = SessionLocal()
    yield db
    db.close()


@pytest.fixture
def auth_test_users(db_session: Session):
    """Seed test users for auth routes."""
    db = db_session
    db.query(User).filter(User.username.in_(["auth_test_admin", "auth_test_analyst"])).delete(synchronize_session=False)
    db.commit()

    admin = User(
        username="auth_test_admin",
        email="admin_auth@dataghost.test",
        hashed_password=get_password_hash("AdminSecret123!"),
        role="admin",
        is_active=True,
    )
    analyst = User(
        username="auth_test_analyst",
        email="analyst_auth@dataghost.test",
        hashed_password=get_password_hash("AnalystSecret123!"),
        role="analyst",
        is_active=True,
    )
    db.add(admin)
    db.add(analyst)
    db.commit()
    db.refresh(admin)
    db.refresh(analyst)

    return {"admin": admin, "analyst": analyst}


def test_login_success(client: TestClient, auth_test_users):
    """Test successful login returns access_token, username, and DB-stored role."""
    res = client.post(
        "/api/auth/login",
        json={"username": "auth_test_analyst", "password": "AnalystSecret123!"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["username"] == "auth_test_analyst"
    assert data["role"] == "analyst"


def test_login_invalid_password(client: TestClient, auth_test_users):
    """Test login with wrong password returns 401."""
    res = client.post(
        "/api/auth/login",
        json={"username": "auth_test_analyst", "password": "WrongPassword!"},
    )
    assert res.status_code == 401


def test_get_me_with_valid_jwt(client: TestClient, auth_test_users):
    """Test GET /auth/me returns full user profile including id, email, username, role."""
    token = create_access_token({"sub": "auth_test_admin"})
    res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["username"] == "auth_test_admin"
    assert data["role"] == "admin"
    assert data["email"] == "admin_auth@dataghost.test"
    assert "id" in data


def test_get_me_unauthorized_without_token(client: TestClient):
    """Test GET /auth/me without authorization header returns 401."""
    res = client.get("/api/auth/me")
    assert res.status_code == 401


def test_get_me_unauthorized_invalid_token(client: TestClient):
    """Test GET /auth/me with invalid token returns 401."""
    res = client.get("/api/auth/me", headers={"Authorization": "Bearer invalid_junk_token"})
    assert res.status_code == 401


def test_role_reverification_reflects_db_update(client: TestClient, auth_test_users, db_session: Session):
    """Test that modifying role in database is immediately verified by GET /auth/me."""
    user = auth_test_users["analyst"]
    token = create_access_token({"sub": user.username})

    # Initially analyst
    res1 = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res1.status_code == 200
    assert res1.json()["role"] == "analyst"

    # Update role to admin in DB
    db_user = db_session.query(User).filter(User.username == user.username).first()
    db_user.role = "admin"
    db_session.commit()

    # Re-verify via /auth/me
    res2 = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res2.status_code == 200
    assert res2.json()["role"] == "admin"
