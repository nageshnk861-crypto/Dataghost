"""
Tests for the AI explanation endpoint (/api/ai/explain).

Covers:
- Unauthenticated requests are rejected with 401.
- Ollama-offline path returns a rule-based explanation (ollama_used: false).
- Explanation text is non-empty and contains key context from the request.
- /api/ai/status returns the expected structure.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Fixtures — import app after patching heavy startup side-effects.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def client():
    with (
        patch("firebase_auth.initialize_firebase_admin", return_value=None),
        patch("database.init_db", return_value=None),
        patch("os.environ.get", side_effect=lambda k, d=None: {
            "RENDER": None,
            "DEFAULT_ADMIN_PASSWORD": "TestPass123!",
            "DATAGHOST_SEED_DEMO": None,
        }.get(k, d)),
    ):
        from main import app
        return TestClient(app)


@pytest.fixture()
def auth_token(client):
    """Create a test admin user and return a JWT token."""
    import os, sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from database import SessionLocal
    from models import User
    from auth import get_password_hash, create_access_token

    db = SessionLocal()
    try:
        username = "ai_test_admin"
        user = db.query(User).filter_by(username=username).first()
        if not user:
            user = User(
                username=username,
                email="ai_test@dataghost.local",
                hashed_password=get_password_hash("TestPass123!"),
                role="admin",
                is_active=True,
            )
            db.add(user)
            db.commit()
        token = create_access_token({"sub": username})
        return token
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_REQUEST = {
    "filename": "customers_india.csv",
    "classification": "CONFIDENTIAL",
    "risk_score": 94,
    "severity": "CRITICAL",
    "action_taken": "BLOCKED",
    "destination": "USB Drive",
    "user": "employee01",
    "findings": [
        {"category": "PII", "severity": "HIGH", "count": 1842, "description": "Aadhaar numbers"},
        {"category": "CREDENTIALS", "severity": "CRITICAL", "count": 3, "description": "API keys"},
    ],
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAiExplainEndpoint:
    """POST /api/ai/explain"""

    def test_unauthenticated_returns_401(self, client):
        r = client.post("/api/ai/explain", json=SAMPLE_REQUEST)
        assert r.status_code == 401

    def test_ollama_offline_returns_rule_based_fallback(self, client, auth_token):
        """When Ollama is unreachable, endpoint returns a rule-based explanation."""
        # Patch _check_ollama to simulate Ollama being offline.
        with patch("api.ai_routes._check_ollama", new_callable=AsyncMock) as mock_check:
            mock_check.return_value = {"available": False, "models": []}

            r = client.post(
                "/api/ai/explain",
                json=SAMPLE_REQUEST,
                headers={"Authorization": f"Bearer {auth_token}"},
            )

        assert r.status_code == 200
        data = r.json()
        assert data["ollama_used"] is False
        assert data["model"] == "rule-based"
        assert len(data["explanation"]) > 20
        assert data["available"] is False

    def test_fallback_explanation_contains_key_context(self, client, auth_token):
        """Rule-based fallback should mention the filename and classification."""
        with patch("api.ai_routes._check_ollama", new_callable=AsyncMock) as mock_check:
            mock_check.return_value = {"available": False, "models": []}

            r = client.post(
                "/api/ai/explain",
                json=SAMPLE_REQUEST,
                headers={"Authorization": f"Bearer {auth_token}"},
            )

        data = r.json()
        explanation = data["explanation"].lower()
        assert "customers_india.csv" in explanation or "pii" in explanation or "confidential" in explanation

    def test_ollama_online_returns_generated_text(self, client, auth_token):
        """When Ollama returns a response, it is forwarded as-is."""
        with (
            patch("api.ai_routes._check_ollama", new_callable=AsyncMock) as mock_check,
            patch("api.ai_routes._generate", new_callable=AsyncMock) as mock_gen,
        ):
            mock_check.return_value = {"available": True, "models": ["gemma2:2b"]}
            mock_gen.return_value = (
                "The file customers_india.csv was flagged because it contains "
                "1,842 Aadhaar numbers and 3 exposed API credentials. "
                "Transferring such data to a USB drive poses a critical exfiltration risk. "
                "The transfer was blocked; the security team should audit this user's activity."
            )

            r = client.post(
                "/api/ai/explain",
                json=SAMPLE_REQUEST,
                headers={"Authorization": f"Bearer {auth_token}"},
            )

        assert r.status_code == 200
        data = r.json()
        assert data["ollama_used"] is True
        assert "1,842" in data["explanation"] or "blocked" in data["explanation"].lower()
        assert data["available"] is True

    def test_empty_findings_still_returns_explanation(self, client, auth_token):
        """Endpoint handles requests with no findings gracefully."""
        body = {
            "filename": "report.pdf",
            "classification": "INTERNAL",
            "risk_score": 12,
            "severity": "LOW",
            "action_taken": "ALLOWED",
        }
        with patch("api.ai_routes._check_ollama", new_callable=AsyncMock) as mock_check:
            mock_check.return_value = {"available": False, "models": []}
            r = client.post(
                "/api/ai/explain",
                json=body,
                headers={"Authorization": f"Bearer {auth_token}"},
            )

        assert r.status_code == 200
        assert len(r.json()["explanation"]) > 10

    def test_partial_body_does_not_crash(self, client, auth_token):
        """Minimal body with only filename is accepted."""
        with patch("api.ai_routes._check_ollama", new_callable=AsyncMock) as mock_check:
            mock_check.return_value = {"available": False, "models": []}
            r = client.post(
                "/api/ai/explain",
                json={"filename": "mystery.docx"},
                headers={"Authorization": f"Bearer {auth_token}"},
            )
        assert r.status_code == 200


class TestAiStatusEndpoint:
    """GET /api/ai/status"""

    def test_unauthenticated_returns_401(self, client):
        r = client.get("/api/ai/status")
        assert r.status_code == 401

    def test_ollama_offline_status(self, client, auth_token):
        with patch("api.ai_routes._check_ollama", new_callable=AsyncMock) as mock_check:
            mock_check.return_value = {"available": False, "models": []}
            r = client.get(
                "/api/ai/status",
                headers={"Authorization": f"Bearer {auth_token}"},
            )

        assert r.status_code == 200
        data = r.json()
        assert data["available"] is False
        assert "url" in data
        assert "model" in data
        assert "models" in data
        assert isinstance(data["message"], str)

    def test_ollama_online_status(self, client, auth_token):
        with patch("api.ai_routes._check_ollama", new_callable=AsyncMock) as mock_check:
            mock_check.return_value = {"available": True, "models": ["gemma2:2b", "llama3.2:latest"]}
            r = client.get(
                "/api/ai/status",
                headers={"Authorization": f"Bearer {auth_token}"},
            )

        assert r.status_code == 200
        data = r.json()
        assert data["available"] is True
        assert "gemma2:2b" in data["models"]
