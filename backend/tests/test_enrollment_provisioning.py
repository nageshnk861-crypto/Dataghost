"""
Tests for Device Provisioning API endpoints.

Covers:
- Provisioning record creation with valid platform/org
- Token hashing (never plaintext storage)
- Expiration and revocation
- RBAC enforcement (admin-only creation)
- Platform validation
"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from main import app
from database import SessionLocal
from models import DeviceProvisioning, User, EnrollmentToken
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
    """Create a test admin user."""
    db = db_session
    
    # Clean up existing test user
    existing = db.query(User).filter(User.username == "test_admin").first()
    if existing:
        db.delete(existing)
        db.commit()
    
    user = User(
        username="test_admin",
        email="admin@test.local",
        hashed_password=get_password_hash("password123"),
        role="admin",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def analyst_user(db_session: Session) -> User:
    """Create a test analyst user (non-admin)."""
    db = db_session
    
    # Clean up existing test user
    existing = db.query(User).filter(User.username == "test_analyst").first()
    if existing:
        db.delete(existing)
        db.commit()
    
    user = User(
        username="test_analyst",
        email="analyst@test.local",
        hashed_password=get_password_hash("password123"),
        role="analyst",
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
def analyst_token(analyst_user: User) -> str:
    """Create analyst JWT token."""
    return create_access_token({"sub": analyst_user.username, "role": analyst_user.role})


# ---------------------------------------------------------------------------
# Provisioning Creation Tests
# ---------------------------------------------------------------------------

def test_create_provisioning_with_valid_data(client: TestClient, admin_token: str, db_session: Session):
    """Test POST /device-provisioning/create with valid organization and platform."""
    db = db_session
    
    response = client.post(
        "/api/v1/device-provisioning/create",
        json={
            "organization_id": "test-org",
            "enrollment_policy_id": "policy-001",
            "platform": "Windows",
            "provisioning_method": "AUTOMATIC_ENROLLMENT",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    data = response.json()
    
    # Verify response structure
    assert "provisioning_id" in data
    assert "bootstrap_token" in data
    assert data["bootstrap_token"] is not None
    assert len(data["bootstrap_token"]) > 0
    assert data["platform"] == "Windows"
    assert data["status"] == "ACTIVE"
    
    # Verify token is hashed in database (never plaintext)
    db_record = db.query(DeviceProvisioning).filter(
        DeviceProvisioning.id == data["provisioning_id"]
    ).first()
    assert db_record is not None
    assert db_record.bootstrap_token_hash is not None
    
    # Verify token hash is not the raw token (i.e., hashed, not plaintext)
    token_hash = hashlib.sha256(data["bootstrap_token"].encode("utf-8")).hexdigest()
    assert db_record.bootstrap_token_hash == token_hash
    assert db_record.bootstrap_token_hash != data["bootstrap_token"]


def test_create_provisioning_android_platform(client: TestClient, admin_token: str):
    """Test provisioning creation for Android platform."""
    response = client.post(
        "/api/v1/device-provisioning/create",
        json={
            "organization_id": "test-org",
            "enrollment_policy_id": "policy-001",
            "platform": "Android",
            "provisioning_method": "AUTOMATIC_ENROLLMENT",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["platform"] == "Android"


def test_create_provisioning_ios_platform(client: TestClient, admin_token: str):
    """Test provisioning creation for iOS platform."""
    response = client.post(
        "/api/v1/device-provisioning/create",
        json={
            "organization_id": "test-org",
            "enrollment_policy_id": "policy-001",
            "platform": "iOS",
            "provisioning_method": "AUTOMATIC_ENROLLMENT",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["platform"] == "iOS"


def test_create_provisioning_macos_platform(client: TestClient, admin_token: str):
    """Test provisioning creation for macOS platform."""
    response = client.post(
        "/api/v1/device-provisioning/create",
        json={
            "organization_id": "test-org",
            "enrollment_policy_id": "policy-001",
            "platform": "macOS",
            "provisioning_method": "AUTOMATIC_ENROLLMENT",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["platform"] == "macOS"


# ---------------------------------------------------------------------------
# Token Hashing Tests
# ---------------------------------------------------------------------------

def test_token_hashing_never_plaintext(client: TestClient, admin_token: str, db_session: Session):
    """Test that bootstrap tokens are hashed, never stored plaintext."""
    db = db_session
    
    response = client.post(
        "/api/v1/device-provisioning/create",
        json={
            "organization_id": "test-org",
            "enrollment_policy_id": "policy-001",
            "platform": "Windows",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    
    assert response.status_code == 200
    data = response.json()
    raw_token = data["bootstrap_token"]
    
    # Query database for hashed token
    db_records = db.query(DeviceProvisioning).all()
    
    # Verify no record contains plaintext token
    for record in db_records:
        assert record.bootstrap_token_hash != raw_token
        assert record.bootstrap_token_hash is not None


def test_different_tokens_have_different_hashes(client: TestClient, admin_token: str, db_session: Session):
    """Test that generating provisioning twice creates different token hashes."""
    db = db_session
    
    # Create first provisioning
    response1 = client.post(
        "/api/v1/device-provisioning/create",
        json={
            "organization_id": "test-org",
            "enrollment_policy_id": "policy-001",
            "platform": "Windows",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response1.status_code == 200
    token1 = response1.json()["bootstrap_token"]
    
    # Create second provisioning
    response2 = client.post(
        "/api/v1/device-provisioning/create",
        json={
            "organization_id": "test-org",
            "enrollment_policy_id": "policy-001",
            "platform": "Windows",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response2.status_code == 200
    token2 = response2.json()["bootstrap_token"]
    
    # Tokens should be different
    assert token1 != token2
    
    # Hashes should be different
    hash1 = hashlib.sha256(token1.encode("utf-8")).hexdigest()
    hash2 = hashlib.sha256(token2.encode("utf-8")).hexdigest()
    assert hash1 != hash2


# ---------------------------------------------------------------------------
# Expiration Tests
# ---------------------------------------------------------------------------

def test_provisioning_expiration_tracking(client: TestClient, admin_token: str, db_session: Session):
    """Test that provisioning records can have expiration dates."""
    db = db_session
    
    response = client.post(
        "/api/v1/device-provisioning/create",
        json={
            "organization_id": "test-org",
            "enrollment_policy_id": "policy-001",
            "platform": "Windows",
            "expires_in_minutes": 1440,  # 24 hours
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    
    assert response.status_code == 200
    data = response.json()
    prov_id = data["provisioning_id"]
    
    # Verify expiration is set in database
    db_record = db.query(DeviceProvisioning).filter(
        DeviceProvisioning.id == prov_id
    ).first()
    assert db_record is not None
    assert db_record.expires_at is not None


def test_provisioning_default_expiration(client: TestClient, admin_token: str, db_session: Session):
    """Test that provisioning records have default expiration if not specified."""
    db = db_session
    
    response = client.post(
        "/api/v1/device-provisioning/create",
        json={
            "organization_id": "test-org",
            "enrollment_policy_id": "policy-001",
            "platform": "Windows",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    
    assert response.status_code == 200
    data = response.json()
    prov_id = data["provisioning_id"]
    
    # Verify default expiration is set
    db_record = db.query(DeviceProvisioning).filter(
        DeviceProvisioning.id == prov_id
    ).first()
    assert db_record is not None
    assert db_record.expires_at is not None
    
    # Default should be reasonable (not already expired)
    now = datetime.now(timezone.utc)
    assert db_record.expires_at > now


# ---------------------------------------------------------------------------
# Revocation Tests
# ---------------------------------------------------------------------------

def test_revoke_provisioning_endpoint(client: TestClient, admin_token: str, db_session: Session):
    """Test POST /device-provisioning/{id}/revoke endpoint."""
    db = db_session
    
    # Create provisioning
    response = client.post(
        "/api/v1/device-provisioning/create",
        json={
            "organization_id": "test-org",
            "enrollment_policy_id": "policy-001",
            "platform": "Windows",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    prov_id = response.json()["provisioning_id"]
    
    # Revoke it
    revoke_response = client.post(
        f"/api/v1/device-provisioning/{prov_id}/revoke",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    
    assert revoke_response.status_code == 200
    
    # Verify status is REVOKED in database
    db_record = db.query(DeviceProvisioning).filter(
        DeviceProvisioning.id == prov_id
    ).first()
    assert db_record is not None
    assert db_record.status == "REVOKED"
    assert db_record.revoked_at is not None


# ---------------------------------------------------------------------------
# RBAC (Role-Based Access Control) Tests
# ---------------------------------------------------------------------------

def test_non_admin_cannot_create_provisioning(client: TestClient, analyst_token: str):
    """Test that non-admin users cannot create provisioning records."""
    response = client.post(
        "/api/v1/device-provisioning/create",
        json={
            "organization_id": "test-org",
            "enrollment_policy_id": "policy-001",
            "platform": "Windows",
        },
        headers={"Authorization": f"Bearer {analyst_token}"},
    )
    
    # Should be 403 Forbidden
    assert response.status_code == 403
    assert "admin" in response.json()["detail"].lower()


def test_missing_authorization_header_returns_401(client: TestClient):
    """Test that missing Authorization header returns 401."""
    response = client.post(
        "/api/v1/device-provisioning/create",
        json={
            "organization_id": "test-org",
            "enrollment_policy_id": "policy-001",
            "platform": "Windows",
        },
    )
    
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Platform Validation Tests
# ---------------------------------------------------------------------------

def test_invalid_platform_returns_400(client: TestClient, admin_token: str):
    """Test that invalid platform name returns 400 Bad Request."""
    response = client.post(
        "/api/v1/device-provisioning/create",
        json={
            "organization_id": "test-org",
            "enrollment_policy_id": "policy-001",
            "platform": "INVALID_PLATFORM",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    
    assert response.status_code == 400
    assert "platform" in response.json()["detail"].lower()


def test_missing_required_fields_returns_422(client: TestClient, admin_token: str):
    """Test that missing required fields returns 422 Unprocessable Entity."""
    response = client.post(
        "/api/v1/device-provisioning/create",
        json={
            "organization_id": "test-org",
            # Missing: enrollment_policy_id and platform
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Provisioning Listing Tests
# ---------------------------------------------------------------------------

def test_list_provisioning_records(client: TestClient, admin_token: str, db_session: Session):
    """Test GET /device-provisioning endpoint."""
    db = db_session
    
    # Create a provisioning record
    response = client.post(
        "/api/v1/device-provisioning/create",
        json={
            "organization_id": "test-org",
            "enrollment_policy_id": "policy-001",
            "platform": "Windows",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    
    # List provisioning records
    list_response = client.get(
        "/api/v1/device-provisioning",
        params={"organization_id": "test-org"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    
    assert list_response.status_code == 200
    data = list_response.json()
    assert "provisioning_records" in data or isinstance(data, list)
