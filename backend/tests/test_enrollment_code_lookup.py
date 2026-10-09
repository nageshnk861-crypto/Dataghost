"""
Tests for enrollment code lookup and public enrollment endpoints.
Regression tests for "enrollment code not found" bug.

These tests verify that:
1. Enrollment codes can be generated and immediately queried
2. The status endpoint works correctly for public (unauthenticated) requests
3. Case sensitivity is handled properly
4. Expired codes are detected
5. Invalid codes return 404
"""

import pytest
from datetime import timedelta, datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from models import User, EnrollmentToken
from database import Base, engine, get_db
from main import app
from auth import get_password_hash


def _utc_now() -> datetime:
    """Get current time in UTC."""
    return datetime.now(timezone.utc)


@pytest.fixture
def db_session():
    """Create a fresh database session for each test."""
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


class TestEnrollmentCodeLookup:
    """Test enrollment code generation and lookup."""

    def test_create_easy_enrollment_then_lookup_immediately(self, client, auth_token):
        """
        Regression test for: "Enrollment code not found"
        
        Scenario:
        1. Admin creates an easy enrollment code
        2. Code is immediately accessible via status endpoint
        3. Status should be PENDING (not consumed)
        """
        # Create enrollment
        create_resp = client.post(
            "/api/devices/enrollment/create-easy",
            json={"platform": "Android"},
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert create_resp.status_code == 200
        data = create_resp.json()
        code = data["enrollment_code"]
        
        # Immediately query status (without authentication)
        status_resp = client.get(f"/api/devices/enrollment/status/{code}")
        assert status_resp.status_code == 200, f"Expected 200 but got {status_resp.status_code}: {status_resp.text}"
        status_data = status_resp.json()
        
        # Verify response
        assert status_data["enrollment_code"] == code
        assert status_data["status"] == "PENDING"
        assert status_data["platform"] == "Android"
        print(f"[PASS] Code {code} found immediately after creation")

    def test_enrollment_code_case_normalization(self, client, auth_token, db_session):
        """
        Test that enrollment codes handle case correctly.
        
        The code is generated as uppercase (DG-XXXX-XXXX).
        Queries should match regardless of case.
        """
        # Create enrollment
        create_resp = client.post(
            "/api/devices/enrollment/create-easy",
            json={"platform": "Android"},
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert create_resp.status_code == 200
        code_upper = create_resp.json()["enrollment_code"]
        code_lower = code_upper.lower()
        code_mixed = code_upper[:3] + code_upper[3:].lower()
        
        # Query with uppercase (should work)
        resp_upper = client.get(f"/api/devices/enrollment/status/{code_upper}")
        assert resp_upper.status_code == 200
        
        # Query with lowercase (should work - backend normalizes)
        resp_lower = client.get(f"/api/devices/enrollment/status/{code_lower}")
        assert resp_lower.status_code == 200, f"Expected 200 for lowercase code but got {resp_lower.status_code}"
        
        # Query with mixed case (should work)
        resp_mixed = client.get(f"/api/devices/enrollment/status/{code_mixed}")
        assert resp_mixed.status_code == 200, f"Expected 200 for mixed case code but got {resp_mixed.status_code}"
        
        # All should return the same enrollment
        assert resp_upper.json()["enrollment_code"] == code_upper
        assert resp_lower.json()["enrollment_code"] == code_upper  # Backend returns normalized
        assert resp_mixed.json()["enrollment_code"] == code_upper
        print(f"[PASS] Case handling works correctly")

    def test_enrollment_code_not_consumed_by_status_check(self, client, auth_token):
        """
        Test that checking status does NOT consume the enrollment code.
        
        The code should only be marked USED after successful device registration,
        not by simply checking the status.
        """
        # Create enrollment
        create_resp = client.post(
            "/api/devices/enrollment/create-easy",
            json={"platform": "Android"},
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        code = create_resp.json()["enrollment_code"]
        
        # Check status multiple times
        for i in range(5):
            status_resp = client.get(f"/api/devices/enrollment/status/{code}")
            assert status_resp.status_code == 200
            status_data = status_resp.json()
            assert status_data["status"] == "PENDING", f"Status should remain PENDING but got {status_data['status']} on iteration {i+1}"
        
        print(f"[PASS] Status check does not consume code (checked 5 times)")

    def test_invalid_enrollment_code_returns_404(self, client):
        """Test that querying an invalid code returns 404."""
        invalid_code = "DG-XXXX-XXXX"
        resp = client.get(f"/api/devices/enrollment/status/{invalid_code}")
        assert resp.status_code == 404
        print(f"[PASS] Invalid code returns 404")

    def test_expired_enrollment_code_returns_valid_with_expired_flag(self, client, auth_token, db_session):
        """
        Test that expired codes are properly detected.
        
        When querying an expired code:
        - Should return 200 (code exists)
        - Should have is_expired = true
        - Status should be EXPIRED
        """
        # Create enrollment
        create_resp = client.post(
            "/api/devices/enrollment/create-easy",
            json={"platform": "Android"},
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        code = create_resp.json()["enrollment_code"]
        
        # Manually expire the token in database
        token = db_session.query(EnrollmentToken).filter(
            EnrollmentToken.enrollment_code == code
        ).first()
        token.expires_at = _utc_now() - timedelta(minutes=1)
        db_session.commit()
        
        # Query should still return 200 but show as expired
        resp = client.get(f"/api/devices/enrollment/status/{code}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_expired"] == True
        assert data["status"] == "EXPIRED"
        print(f"[PASS] Expired code properly marked as EXPIRED")

    def test_enrollment_code_persistence_across_requests(self, client, auth_token):
        """
        Test that enrollment codes persist and are accessible.
        
        This is a regression test for cases where records were being
        created but not properly committed or in wrong database session.
        """
        codes = []
        
        # Create 3 enrollment codes
        for i in range(3):
            resp = client.post(
                "/api/devices/enrollment/create-easy",
                json={"platform": "Android"},
                headers={"Authorization": f"Bearer {auth_token}"}
            )
            assert resp.status_code == 200
            code = resp.json()["enrollment_code"]
            codes.append(code)
        
        # Verify all are accessible
        for code in codes:
            resp = client.get(f"/api/devices/enrollment/status/{code}")
            assert resp.status_code == 200, f"Code {code} not found"
            data = resp.json()
            assert data["enrollment_code"] == code
        
        print(f"[PASS] All {len(codes)} codes persisted and accessible")

    def test_enrollment_code_url_encoding_in_path(self, client, auth_token):
        """
        Test that enrollment codes work correctly when URL-encoded.
        
        Hyphens in codes (DG-XXXX-XXXX) should be properly handled.
        """
        resp = client.post(
            "/api/devices/enrollment/create-easy",
            json={"platform": "Android"},
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        code = resp.json()["enrollment_code"]
        
        # Query with proper URL encoding of hyphens (should be transparent)
        encoded_code = code.replace("-", "%2D")
        status_resp = client.get(f"/api/devices/enrollment/status/{encoded_code}")
        assert status_resp.status_code == 200
        assert status_resp.json()["enrollment_code"] == code
        print(f"[PASS] URL encoding handled correctly")

    def test_public_endpoint_no_authentication_required(self, client, db_session):
        """
        Test that the status endpoint is truly public (no auth required).
        
        This endpoint should be accessible by frontend /enroll/[code] page
        without any authentication token.
        """
        # Create enrollment in database directly (simulating a created code)
        token = EnrollmentToken(
            token_hash="dummy_hash_" + "x" * 50,
            enrollment_code="DG-TEST-0001",
            platform="Android",
            organization_id="test-org",
            created_by="test_admin",
            expires_at=_utc_now() + timedelta(minutes=10),
            status="PENDING",
        )
        db_session.add(token)
        db_session.commit()
        
        # Query WITHOUT any authorization header
        resp = client.get("/api/devices/enrollment/status/DG-TEST-0001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["enrollment_code"] == "DG-TEST-0001"
        assert data["status"] == "PENDING"
        print(f"[PASS] Public endpoint accessible without authentication")
