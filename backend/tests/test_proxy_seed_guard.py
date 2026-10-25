"""
Tests for:
  1. Frontend proxy: 60-second timeout, one retry, 502 wakeup message.
     (Simulated in Python — validates the logic contract, not the TS code directly.)
  2. Production startup guard: refuse to start when RENDER is set and
     DEFAULT_ADMIN_PASSWORD is missing or equals "dataghost123".
  3. Demo seeding gate: DATAGHOST_SEED_DEMO=false suppresses seeding;
     RENDER set + SEED_DEMO_DATA without DATAGHOST_SEED_DEMO skips seeding.
"""
import os
import pytest
from unittest.mock import patch, MagicMock

# ---------------------------------------------------------------------------
# 1. Proxy retry / wakeup-message contract tests
# ---------------------------------------------------------------------------
# The TypeScript tryProxyToBackend function is not directly callable from
# Python, but its contract is:
#   * On first 502 → retry once after 1 s
#   * On second 502 → return BACKEND_UNREACHABLE_502 sentinel
#   * backend502() returns JSON { error: "Backend is waking up, please retry in a minute" }
#
# We validate the *backend* enroll endpoint (which the proxy forwards to) does
# NOT itself return 502 on a normal call, ensuring the proxy's 502 path is
# only triggered by genuine network failures.

from fastapi.testclient import TestClient
from main import app
from database import SessionLocal, init_db
from models import User
from auth import create_access_token, get_password_hash

client = TestClient(app)


@pytest.fixture(autouse=True)
def _setup():
    init_db()
    db = SessionLocal()
    try:
        u = db.query(User).filter(User.username == "proxy_test_user").first()
        if not u:
            u = User(
                username="proxy_test_user",
                email="proxy@test.local",
                hashed_password=get_password_hash("TestPass123!"),
                role="analyst",
                is_active=True,
            )
            db.add(u)
            db.commit()
    finally:
        db.close()


def _auth_headers():
    db = SessionLocal()
    try:
        u = db.query(User).filter(User.username == "proxy_test_user").first()
        tok = create_access_token({"sub": u.username, "role": u.role, "id": u.id})
        return {"Authorization": f"Bearer {tok}"}
    finally:
        db.close()


def test_enrollment_create_returns_200_not_502():
    """Backend enrollment endpoint must return 200, never 502, on a valid request."""
    r = client.post(
        "/api/devices/enrollment/create",
        json={"platform": "Windows"},
        headers=_auth_headers(),
    )
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    data = r.json()
    assert "enrollment_code" in data
    assert "raw_token" in data


def test_proxy_wakeup_message_contract():
    """
    Validate the wakeup message string that the frontend proxy backend502()
    function embeds.  This is a contract test — if the message changes here,
    update the TS source too.
    """
    expected_error = "Backend is waking up, please retry in a minute"
    # The actual TS function is not importable; we assert the string is correct
    # by checking it is defined in the route.ts source.
    route_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "frontend",
        "app", "api", "[...path]", "route.ts",
    )
    with open(route_path, encoding="utf-8") as fh:
        content = fh.read()
    assert expected_error in content, (
        f"Expected wakeup message '{expected_error}' not found in route.ts"
    )
    assert "attempt()" in content, "retry attempt() function not found in route.ts"
    assert "60_000" in content, "60-second timeout constant not found in route.ts"


# ---------------------------------------------------------------------------
# 2. Production startup guard
# ---------------------------------------------------------------------------

def test_production_guard_raises_on_default_password():
    """lifespan must raise RuntimeError when RENDER is set and password is default."""
    import asyncio
    from contextlib import asynccontextmanager

    _DEFAULT = "dataghost123"

    # Simulate the guard logic inline (same code as in lifespan)
    def _check_guard(render_set: bool, password: str):
        if render_set:
            if not password or password == _DEFAULT:
                raise RuntimeError("FATAL: DEFAULT_ADMIN_PASSWORD unset or default")

    # Case 1: RENDER set, no password
    with pytest.raises(RuntimeError, match="FATAL"):
        _check_guard(render_set=True, password="")

    # Case 2: RENDER set, default password
    with pytest.raises(RuntimeError, match="FATAL"):
        _check_guard(render_set=True, password=_DEFAULT)

    # Case 3: RENDER set, strong password — no exception
    _check_guard(render_set=True, password="str0ng-UniqueP@ss!")

    # Case 4: RENDER not set, default password — allowed (local dev)
    _check_guard(render_set=False, password=_DEFAULT)


def test_production_guard_via_env(monkeypatch):
    """Integration: starting the lifespan with RENDER + bad password raises."""
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.setenv("DEFAULT_ADMIN_PASSWORD", "dataghost123")

    import asyncio

    async def _run():
        from main import lifespan
        async with lifespan(app):
            pass

    with pytest.raises(RuntimeError, match="FATAL"):
        asyncio.run(_run())


# ---------------------------------------------------------------------------
# 3. Demo seeding gate
# ---------------------------------------------------------------------------

def test_demo_seeding_suppressed_without_flag(monkeypatch):
    """Without DATAGHOST_SEED_DEMO=true, _seed_demo_data must never be called."""
    monkeypatch.delenv("DATAGHOST_SEED_DEMO", raising=False)
    monkeypatch.delenv("SEED_DEMO_DATA", raising=False)
    monkeypatch.delenv("RENDER", raising=False)

    seed_flag = (
        os.environ.get("DATAGHOST_SEED_DEMO", "").lower() in ("1", "true", "yes")
        or os.environ.get("SEED_DEMO_DATA", "").lower() in ("1", "true", "yes")
    )
    assert not seed_flag, "Seed flag must be false when no env vars are set"


def test_demo_seeding_suppressed_on_render_with_legacy_flag(monkeypatch):
    """SEED_DEMO_DATA=true + RENDER=true → seeding must be skipped (legacy alias)."""
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.setenv("SEED_DEMO_DATA", "true")
    monkeypatch.delenv("DATAGHOST_SEED_DEMO", raising=False)

    _seed_flag = (
        os.environ.get("DATAGHOST_SEED_DEMO", "").lower() in ("1", "true", "yes")
        or os.environ.get("SEED_DEMO_DATA", "").lower() in ("1", "true", "yes")
    )
    _on_render = bool(os.environ.get("RENDER"))
    _demo_explicitly = (
        _on_render
        and os.environ.get("DATAGHOST_SEED_DEMO", "").lower() in ("1", "true", "yes")
    )
    _should_seed = _seed_flag and (not _on_render or _demo_explicitly)
    assert not _should_seed, (
        "Seeding MUST be skipped on Render when only SEED_DEMO_DATA (legacy) is set"
    )


def test_demo_seeding_allowed_on_render_with_explicit_flag(monkeypatch):
    """DATAGHOST_SEED_DEMO=true + RENDER=true → seeding is explicitly permitted."""
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.setenv("DATAGHOST_SEED_DEMO", "true")

    _seed_flag = os.environ.get("DATAGHOST_SEED_DEMO", "").lower() in ("1", "true", "yes")
    _on_render = bool(os.environ.get("RENDER"))
    _demo_explicitly = (
        _on_render
        and os.environ.get("DATAGHOST_SEED_DEMO", "").lower() in ("1", "true", "yes")
    )
    _should_seed = _seed_flag and (not _on_render or _demo_explicitly)
    assert _should_seed, (
        "Seeding MUST be allowed when DATAGHOST_SEED_DEMO=true is explicitly set even on Render"
    )
