"""
Tests for Firebase token verification, Firebase Admin initialization, and FastAPI integration.

Updated to mock google.oauth2.id_token.verify_firebase_token (the new primary
verification path that does not require a service-account private key).
"""
from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient

from main import app
from firebase_auth import initialize_firebase_admin, verify_firebase_token
from database import SessionLocal, init_db
from models import User


@pytest.fixture
def client():
    init_db()
    return TestClient(app)


def test_firebase_admin_initialization():
    """Verify Firebase Admin initializes without raising exceptions (idempotent)."""
    # initialize_firebase_admin now returns None (void) — it no longer returns the app.
    # We just verify it doesn't throw.
    try:
        initialize_firebase_admin()
        initialized = True
    except Exception:
        initialized = False
    assert initialized, "initialize_firebase_admin() must not raise"


def test_verify_firebase_token_valid():
    """Verify valid Firebase token decoding via the google-auth public-key path."""
    mock_claims = {
        "uid": "firebase-test-uid-123",
        "sub": "firebase-test-uid-123",
        "email": "firebase_user@example.com",
        "name": "Firebase User",
        "aud": "dataghost-9431f",
    }
    # Patch the google-auth verifier used in our new implementation.
    with patch("firebase_auth._gauth_verify", return_value=mock_claims):
        claims = verify_firebase_token("valid_dummy_firebase_token")
        assert claims is not None
        assert claims["email"] == "firebase_user@example.com"
        # uid should be normalised from sub if not already present
        assert claims.get("uid") == "firebase-test-uid-123"


def test_verify_firebase_token_expired():
    """Verify expired Firebase token returns None."""
    with patch(
        "firebase_auth._gauth_verify",
        side_effect=Exception("Token has expired"),
    ):
        claims = verify_firebase_token("expired_firebase_token")
        assert claims is None


def test_verify_firebase_token_invalid():
    """Verify invalid Firebase token returns None."""
    with patch(
        "firebase_auth._gauth_verify",
        side_effect=ValueError("Invalid token signature"),
    ):
        claims = verify_firebase_token("invalid_firebase_token")
        assert claims is None


def test_verify_firebase_token_empty():
    """Empty or whitespace tokens return None without calling the verifier."""
    assert verify_firebase_token("") is None
    assert verify_firebase_token("   ") is None


def test_authenticated_endpoint_with_firebase_token(client):
    """Test accessing protected route /api/auth/me with a verified Firebase token."""
    mock_claims = {
        "uid": "fb-soc-analyst-999",
        "sub": "fb-soc-analyst-999",
        "email": "soc_analyst@dataghost.local",
        "name": "SOC Analyst",
        "aud": "dataghost-9431f",
    }
    with patch("firebase_auth._gauth_verify", return_value=mock_claims):
        headers = {"Authorization": "Bearer mock_valid_firebase_token"}
        response = client.get("/api/auth/me", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "soc_analyst@dataghost.local"
        assert data["is_active"] is True


def test_authenticated_endpoint_with_invalid_firebase_token(client):
    """Test accessing protected route with invalid token is rejected with 401."""
    with patch(
        "firebase_auth._gauth_verify",
        side_effect=ValueError("Invalid token"),
    ):
        headers = {"Authorization": "Bearer invalid_token_12345"}
        response = client.get("/api/auth/me", headers=headers)
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid or missing authentication token"


def test_existing_jwt_login_still_works(client):
    """Verify traditional DataGhost JWT login and /auth/me work seamlessly."""
    login_resp = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "dataghost123"},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    assert token is not None

    me_resp = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_resp.status_code == 200
    assert me_resp.json()["username"] == "admin"
