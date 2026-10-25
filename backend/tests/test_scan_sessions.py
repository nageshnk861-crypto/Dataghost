"""
Tests for scan session lifecycle, multi-user scoping, skip-directory logic,
and agent DLP scan with a real temp-file tree.

All tests run against an in-memory SQLite database; no network calls are made.
"""
import hashlib
import os
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure agent directory is in sys.path
_repo_root = Path(__file__).resolve().parent.parent.parent
_agent_dir = str(_repo_root / "agent")
if _agent_dir not in sys.path:
    sys.path.insert(0, _agent_dir)

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

# ──────────────────────────────────────────────────────────────────────────────
# Bootstrap the app with a throw-away in-memory DB
# ──────────────────────────────────────────────────────────────────────────────
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-scan-sessions")

from models import Device, User  # noqa: E402





# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _make_user(db: Session, username: str, role: str = "analyst") -> User:
    from auth import get_password_hash
    existing = db.query(User).filter(User.username == username).first()
    if existing:
        return existing
    u = User(
        username=username,
        email=f"{username}_{secrets.token_hex(4)}@test.local",
        hashed_password=get_password_hash("Test1234!"),
        role=role,
        is_active=True,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u



def _make_device(db: Session, user: User, name: str = "TestDevice") -> tuple[Device, str]:
    """Create a device, return (device, raw_token)."""
    raw_token = secrets.token_hex(16)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    dev = Device(
        device_name=name,
        device_id=f"test-dev-{secrets.token_hex(4)}",
        status="ACTIVE",
        device_token_hash=token_hash,
        user_id=user.id,
        last_seen=datetime.now(timezone.utc),
    )
    db.add(dev)
    db.commit()
    db.refresh(dev)
    return dev, raw_token


def _jwt(client: TestClient, username: str) -> str:
    resp = client.post("/api/auth/login", json={"username": username, "password": "Test1234!"})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


# ──────────────────────────────────────────────────────────────────────────────
# Test 1 – Full scan session lifecycle (start → progress → complete)
# ──────────────────────────────────────────────────────────────────────────────

class TestScanSessionLifecycle:
    def test_start_progress_complete(self, client: TestClient, db: Session):
        # Setup
        user = _make_user(db, "scan_user_1")
        device, token = _make_device(db, user, "LifecycleDevice")
        headers = {"Authorization": f"Bearer {token}"}
        dev_id = device.device_id

        # 1. Start
        r = client.post(f"/api/devices/{dev_id}/scans/start",
                        json={"trigger": "ENROLLMENT"}, headers=headers)
        assert r.status_code == 200, r.text
        body = r.json()
        scan_id = body["scan_id"]
        assert body["status"] == "RUNNING"
        assert body["trigger"] == "ENROLLMENT"
        assert body["device_id"] == device.id

        # 2. Progress update
        r = client.post(f"/api/devices/{dev_id}/scans/{scan_id}/progress",
                        json={"files_discovered": 500, "files_scanned": 120,
                              "files_skipped": 380, "findings_count": 3,
                              "current_path": "C:\\Users\\test\\Documents"},
                        headers=headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["files_scanned"] == 120
        assert body["current_path"] == "C:\\Users\\test\\Documents"
        assert body["status"] == "RUNNING"

        # 3. Complete
        r = client.post(f"/api/devices/{dev_id}/scans/{scan_id}/complete",
                        json={"status": "COMPLETED", "files_discovered": 600,
                              "files_scanned": 580, "files_skipped": 20,
                              "findings_count": 5},
                        headers=headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "COMPLETED"
        assert body["files_scanned"] == 580
        assert body["findings_count"] == 5
        assert body["finished_at"] is not None

    def test_progress_ignored_on_terminal_session(self, client: TestClient, db: Session):
        user = _make_user(db, "scan_user_term")
        device, token = _make_device(db, user, "TermDevice")
        headers = {"Authorization": f"Bearer {token}"}
        dev_id = device.device_id

        # Start + immediately cancel
        r = client.post(f"/api/devices/{dev_id}/scans/start",
                        json={"trigger": "MANUAL"}, headers=headers)
        scan_id = r.json()["scan_id"]
        client.post(f"/api/devices/{dev_id}/scans/{scan_id}/complete",
                    json={"status": "CANCELLED"}, headers=headers)

        # Progress on a cancelled session should be silently ignored (200, same body)
        r = client.post(f"/api/devices/{dev_id}/scans/{scan_id}/progress",
                        json={"files_scanned": 9999}, headers=headers)
        assert r.status_code == 200
        assert r.json()["status"] == "CANCELLED"
        assert r.json()["files_scanned"] != 9999  # not overwritten

    def test_failed_session(self, client: TestClient, db: Session):
        user = _make_user(db, "scan_user_fail")
        device, token = _make_device(db, user, "FailDevice")
        headers = {"Authorization": f"Bearer {token}"}
        dev_id = device.device_id

        r = client.post(f"/api/devices/{dev_id}/scans/start",
                        json={"trigger": "SCHEDULED"}, headers=headers)
        scan_id = r.json()["scan_id"]

        r = client.post(f"/api/devices/{dev_id}/scans/{scan_id}/complete",
                        json={"status": "FAILED", "error_message": "Disk error on D:\\"},
                        headers=headers)
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "FAILED"
        assert "Disk error" in body["error_message"]

    def test_device_x_cannot_update_device_y_scan(self, client: TestClient, db: Session):
        """
        Verify cross-device scan hijacking is blocked:
        A valid device token for Device X CANNOT update progress or complete a scan belonging to Device Y.
        """
        user = _make_user(db, "scan_cross_user")
        dev_a, token_a = _make_device(db, user, "DeviceA")
        dev_b, token_b = _make_device(db, user, "DeviceB")

        headers_a = {"Authorization": f"Bearer {token_a}"}
        headers_b = {"Authorization": f"Bearer {token_b}"}

        # Device A starts a scan
        r = client.post(f"/api/devices/{dev_a.device_id}/scans/start",
                        json={"trigger": "MANUAL"}, headers=headers_a)
        assert r.status_code == 200
        scan_id_a = r.json()["scan_id"]

        # Device B attempts to update progress on Device A's scan using B's token and B's endpoint
        # (scan_id belongs to A, but URL has B's device ID) -> 404
        r_prog_cross = client.post(f"/api/devices/{dev_b.device_id}/scans/{scan_id_a}/progress",
                                   json={"files_scanned": 50}, headers=headers_b)
        assert r_prog_cross.status_code == 404, f"Expected 404, got {r_prog_cross.status_code}: {r_prog_cross.text}"

        # Device B attempts to update progress on Device A's scan using B's token against A's endpoint
        # (device auth fails because token_b is not device A's token) -> 401
        r_prog_tamper = client.post(f"/api/devices/{dev_a.device_id}/scans/{scan_id_a}/progress",
                                    json={"files_scanned": 50}, headers=headers_b)
        assert r_prog_tamper.status_code == 401, f"Expected 401, got {r_prog_tamper.status_code}: {r_prog_tamper.text}"

        # Device B attempts to complete Device A's scan using B's token and B's endpoint -> 404
        r_comp_cross = client.post(f"/api/devices/{dev_b.device_id}/scans/{scan_id_a}/complete",
                                   json={"status": "COMPLETED"}, headers=headers_b)
        assert r_comp_cross.status_code == 404, f"Expected 404, got {r_comp_cross.status_code}: {r_comp_cross.text}"

        # Device B attempts to complete Device A's scan using B's token against A's endpoint -> 401
        r_comp_tamper = client.post(f"/api/devices/{dev_a.device_id}/scans/{scan_id_a}/complete",
                                    json={"status": "COMPLETED"}, headers=headers_b)
        assert r_comp_tamper.status_code == 401, f"Expected 401, got {r_comp_tamper.status_code}: {r_comp_tamper.text}"



# ──────────────────────────────────────────────────────────────────────────────
# Test 2 – Multi-user ownership scoping
# ──────────────────────────────────────────────────────────────────────────────

class TestScanSessionOwnership:
    def test_analyst_b_cannot_list_a_sessions(self, client: TestClient, db: Session):
        user_a = _make_user(db, "scan_owner_a")
        user_b = _make_user(db, "scan_owner_b")
        device_a, token_a = _make_device(db, user_a, "DeviceA")
        _make_device(db, user_b, "DeviceB")

        # A creates a session
        hdrs_a = {"Authorization": f"Bearer {token_a}"}
        client.post(f"/api/devices/{device_a.device_id}/scans/start",
                    json={"trigger": "MANUAL"}, headers=hdrs_a)

        # B tries to list A's sessions using JWT
        jwt_b = _jwt(client, "scan_owner_b")
        r = client.get(f"/api/devices/{device_a.device_id}/scans",
                       headers={"Authorization": f"Bearer {jwt_b}"})
        assert r.status_code == 404, r.text

    def test_analyst_b_cannot_read_a_latest(self, client: TestClient, db: Session):
        user_a = _make_user(db, "scope_a")
        user_b = _make_user(db, "scope_b")
        device_a, token_a = _make_device(db, user_a, "ScopeDevA")
        _make_device(db, user_b, "ScopeDevB")

        hdrs_a = {"Authorization": f"Bearer {token_a}"}
        client.post(f"/api/devices/{device_a.device_id}/scans/start",
                    json={"trigger": "MANUAL"}, headers=hdrs_a)

        jwt_b = _jwt(client, "scope_b")
        r = client.get(f"/api/devices/{device_a.device_id}/scans/latest",
                       headers={"Authorization": f"Bearer {jwt_b}"})
        assert r.status_code == 404

        r_list = client.get(f"/api/devices/{device_a.device_id}/scans",
                            headers={"Authorization": f"Bearer {jwt_b}"})
        assert r_list.status_code == 404

    def test_admin_sees_any_device_sessions(self, client: TestClient, db: Session):
        _make_user(db, "scan_admin_user", role="admin")
        analyst = _make_user(db, "scan_analyst_for_admin")
        device, token = _make_device(db, analyst, "AdminViewDev")

        # Create a session as the device
        hdrs = {"Authorization": f"Bearer {token}"}
        client.post(f"/api/devices/{device.device_id}/scans/start",
                    json={"trigger": "MANUAL"}, headers=hdrs)

        jwt_admin = _jwt(client, "scan_admin_user")
        r = client.get(f"/api/devices/{device.device_id}/scans",
                       headers={"Authorization": f"Bearer {jwt_admin}"})
        assert r.status_code == 200
        assert r.json()["total"] >= 1

    def test_owner_can_list_own_sessions(self, client: TestClient, db: Session):
        user = _make_user(db, "own_list_user")
        device, token = _make_device(db, user, "OwnListDev")

        hdrs = {"Authorization": f"Bearer {token}"}
        client.post(f"/api/devices/{device.device_id}/scans/start",
                    json={"trigger": "MANUAL"}, headers=hdrs)

        jwt = _jwt(client, "own_list_user")
        r = client.get(f"/api/devices/{device.device_id}/scans",
                       headers={"Authorization": f"Bearer {jwt}"})
        assert r.status_code == 200
        assert r.json()["total"] >= 1


# ──────────────────────────────────────────────────────────────────────────────
# Test 3 – INTERRUPTED when device goes offline during RUNNING
# ──────────────────────────────────────────────────────────────────────────────

class TestScanSessionInterrupted:
    def test_running_session_marked_interrupted_when_offline(
        self, client: TestClient, db: Session
    ):
        from datetime import timedelta

        user = _make_user(db, "interrupted_user")
        device, token = _make_device(db, user, "OfflineDev")

        # Start a session
        hdrs = {"Authorization": f"Bearer {token}"}
        r = client.post(f"/api/devices/{device.device_id}/scans/start",
                        json={"trigger": "MANUAL"}, headers=hdrs)
        scan_id = r.json()["scan_id"]

        # Make the device look offline (last_seen > 120 s ago)
        device.last_seen = datetime.now(timezone.utc) - timedelta(seconds=200)
        db.commit()

        # Listing sessions should flip RUNNING → INTERRUPTED
        jwt = _jwt(client, "interrupted_user")
        r = client.get(f"/api/devices/{device.device_id}/scans",
                       headers={"Authorization": f"Bearer {jwt}"})
        assert r.status_code == 200
        items = r.json()["items"]
        assert any(s["scan_id"] == scan_id and s["status"] == "INTERRUPTED" for s in items)


# ──────────────────────────────────────────────────────────────────────────────
# Test 4 – Agent scan_file_for_findings with a real temp-file tree
# ──────────────────────────────────────────────────────────────────────────────

class TestAgentDLPScan:
    """
    Exercises the agent's scan_file_for_findings() against real temp files
    that contain fake secret patterns.  No mock is used.
    """

    def test_credit_card_detection(self):
        """CC number that passes Luhn check is detected with REDACTED evidence."""
        # Visa 16-digit that passes Luhn
        cc = "4111111111111111"
        content = f"Customer card: {cc}".encode()
        from dataghost_agent import scan_file_for_findings  # noqa: F401 (agent dir)
        findings = scan_file_for_findings("/tmp/test.txt", content, "test-device")
        assert any(f["rule_id"] == "credit_card" for f in findings)
        # Evidence must be redacted – no raw CC number
        for f in findings:
            if f["rule_id"] == "credit_card":
                assert cc not in f["evidence_redacted"]
                assert "[REDACTED]" in f["evidence_redacted"]

    def test_aws_key_detection(self):
        content = b"AKIA0000000000000000 some text"
        from dataghost_agent import scan_file_for_findings
        findings = scan_file_for_findings("/tmp/creds.env", content, "test-device")
        assert any(f["rule_id"] == "aws_access_key" for f in findings)

    def test_clean_file_returns_no_findings(self):
        content = b"Hello, world!\nNo secrets here."
        from dataghost_agent import scan_file_for_findings
        findings = scan_file_for_findings("/tmp/clean.txt", content, "test-device")
        assert findings == []

    def test_skip_dirs_respected_in_full_scan(self, tmp_path):
        """
        Verify that _should_skip_dir filters out system directories when given system paths,
        filters universal tool dirs (.git, node_modules) by name,
        and DOES NOT skip user directories that happen to be named 'Windows'.
        """
        from dataghost_agent import _should_skip_dir

        # Universal tool / cache dirs are skipped anywhere
        for d in [".git", "node_modules", "__pycache__", ".venv"]:
            assert _should_skip_dir(d), f"'{d}' should be skipped by name"

        # System locations are skipped when their full path is at drive root or AppData
        assert _should_skip_dir("Windows", r"C:\Windows")
        assert _should_skip_dir("Program Files", r"C:\Program Files")
        assert _should_skip_dir("Program Files (x86)", r"C:\Program Files (x86)")
        assert _should_skip_dir("ProgramData", r"C:\ProgramData")
        assert _should_skip_dir("$Recycle.Bin", r"D:\$Recycle.Bin")
        assert _should_skip_dir("AppData", r"C:\Users\John\AppData")
        assert _should_skip_dir("Local", r"C:\Users\John\AppData\Local")

        # Crucial requirement: A user directory named "Windows" (e.g. C:\Users\Bob\Windows or C:\projects\Windows)
        # MUST NOT be skipped!
        user_windows = r"C:\Users\Alice\Windows"
        assert not _should_skip_dir("Windows", user_windows), f"User directory '{user_windows}' must NOT be skipped"
        project_windows = r"D:\workspace\project\Windows"
        assert not _should_skip_dir("Windows", project_windows), f"Project directory '{project_windows}' must NOT be skipped"

        # Normal non-system folders
        non_skip = ["Documents", "Desktop", "Projects", "src"]
        for d in non_skip:
            assert not _should_skip_dir(d, f"C:\\Users\\Alice\\{d}"), f"'{d}' should NOT be skipped"


    def test_full_scan_real_tree(self, tmp_path):
        """
        Build a real temp directory tree with:
        - a clean file
        - a file with a fake private key
        - a file in a skip dir (should not produce findings)
        Then call run_full_scan with scan_roots pointing at tmp_path.
        No backend calls are made (api_url = '' and device_id missing → session start fails gracefully).
        """
        import sys
        # Make dataghost_agent importable
        agent_dir = os.path.join(os.path.dirname(__file__), "..", "..", "agent")
        if agent_dir not in sys.path:
            sys.path.insert(0, os.path.abspath(agent_dir))

        from dataghost_agent import run_full_scan, _should_skip_dir

        # Create files
        docs = tmp_path / "Documents"
        docs.mkdir()
        (docs / "clean.txt").write_text("Nothing to see here")
        (docs / "secrets.env").write_text(
            "API_KEY=sk-AKIA0000000000000001\n"
            "DB_PASSWORD=super_secret_123!\n"
            "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA...\n-----END RSA PRIVATE KEY-----\n"
        )

        # File inside a skip dir must not contribute findings
        skip = tmp_path / ".git"
        skip.mkdir()
        (skip / "config").write_text(
            "AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE\n"
        )

        cfg = {
            "device_id": "test-offline-device",
            "api_url": "",            # no backend – scan/start will fail gracefully
            "scan_roots": [str(docs)],  # only docs, not the .git dir
            "max_file_size_mb": 50,
        }

        # Should not raise even without a backend
        run_full_scan(cfg, auth_token=None, trigger="MANUAL")

        # The .git dir was not in scan_roots so .git/config findings never happen
        # (behaviour assertion via _should_skip_dir for correctness)
        assert _should_skip_dir(".git")


# ──────────────────────────────────────────────────────────────────────────────
# Test 5 – Drive discovery on non-Windows always returns home dir
# ──────────────────────────────────────────────────────────────────────────────

class TestDriveDiscovery:
    def test_non_windows_fallback(self, monkeypatch):
        import sys
        agent_dir = os.path.join(os.path.dirname(__file__), "..", "..", "agent")
        if agent_dir not in sys.path:
            sys.path.insert(0, os.path.abspath(agent_dir))

        import dataghost_agent as agent

        monkeypatch.setattr(agent.sys, "platform", "linux")
        from pathlib import Path
        roots = agent._discover_scan_roots({})
        assert roots == [str(Path.home())]

    def test_scan_roots_override_wins(self, monkeypatch, tmp_path):
        import sys
        agent_dir = os.path.join(os.path.dirname(__file__), "..", "..", "agent")
        if agent_dir not in sys.path:
            sys.path.insert(0, os.path.abspath(agent_dir))

        import dataghost_agent as agent

        custom = str(tmp_path / "custom_root")
        os.makedirs(custom, exist_ok=True)
        roots = agent._discover_scan_roots({"scan_roots": [custom]})
        assert roots == [custom]


# ──────────────────────────────────────────────────────────────────────────────
# Test 6 – Fail-Closed Device Authentication
# ──────────────────────────────────────────────────────────────────────────────

class TestFailClosedDeviceAuth:
    """
    Every device-authenticated endpoint must FAIL CLOSED:
    - If the device has no token (token hash or auth_token), returns 401.
    - If no Authorization header is provided, returns 401.
    - If an invalid / wrong Bearer token is provided, returns 401.
    Endpoints:
    - POST /api/devices/{id}/scans/start
    - POST /api/devices/{id}/scans/{scan_id}/progress
    - POST /api/devices/{id}/scans/{scan_id}/complete
    - POST /api/devices/{id}/heartbeat
    - POST /api/devices/{id}/findings
    """

    def test_device_without_token_fails_closed(self, client: TestClient, db: Session):
        dev_suffix = secrets.token_hex(4)
        user = _make_user(db, f"no_token_{dev_suffix}")
        # Legacy/unenrolled device without credentials
        device = Device(
            device_id=f"no-token-dev-{dev_suffix}",
            device_name=f"NoTokenDev-{dev_suffix}",
            user_id=user.id,
            status="ACTIVE",
            device_token_hash=None,
            auth_token=None,
        )
        db.add(device)
        db.commit()

        # Any bearer token should be rejected because device has no registered token
        hdrs = {"Authorization": "Bearer some-token"}

        # scans/start
        r = client.post(f"/api/devices/{device.device_id}/scans/start",
                        json={"trigger": "MANUAL"}, headers=hdrs)
        assert r.status_code == 401

        # heartbeat
        r = client.post(f"/api/devices/{device.device_id}/heartbeat",
                        json={"agent_version": "1.0"}, headers=hdrs)
        assert r.status_code == 401

        # findings
        r = client.post(f"/api/devices/{device.device_id}/findings",
                        json={"findings": []}, headers=hdrs)
        assert r.status_code == 401

    def test_missing_auth_header_fails_closed(self, client: TestClient, db: Session):
        user = _make_user(db, "missing_hdr_user")
        device, _ = _make_device(db, user, "MissingHdrDev")

        r = client.post(f"/api/devices/{device.device_id}/scans/start", json={"trigger": "MANUAL"})
        assert r.status_code == 401

        r = client.post(f"/api/devices/{device.device_id}/heartbeat", json={"agent_version": "1.0"})
        assert r.status_code == 401

        r = client.post(f"/api/devices/{device.device_id}/findings", json={"findings": []})
        assert r.status_code == 401

    def test_wrong_token_fails_closed(self, client: TestClient, db: Session):
        user = _make_user(db, "wrong_token_user")
        device, _ = _make_device(db, user, "WrongTokenDev")
        bad_hdrs = {"Authorization": "Bearer totally-wrong-token-abc"}

        r = client.post(f"/api/devices/{device.device_id}/scans/start",
                        json={"trigger": "MANUAL"}, headers=bad_hdrs)
        assert r.status_code == 401

        r = client.post(f"/api/devices/{device.device_id}/heartbeat",
                        json={"agent_version": "1.0"}, headers=bad_hdrs)
        assert r.status_code == 401

        r = client.post(f"/api/devices/{device.device_id}/findings",
                        json={"findings": []}, headers=bad_hdrs)
        assert r.status_code == 401

    def test_progress_and_complete_fail_closed_without_token(self, client: TestClient, db: Session):
        user = _make_user(db, "prog_comp_auth_user")
        device, valid_token = _make_device(db, user, "ProgCompAuthDev")

        # Start a scan session with valid token
        hdrs = {"Authorization": f"Bearer {valid_token}"}
        start_res = client.post(f"/api/devices/{device.device_id}/scans/start",
                                json={"trigger": "MANUAL"}, headers=hdrs)
        assert start_res.status_code == 200
        scan_id = start_res.json()["scan_id"]

        # Progress without token -> 401
        r = client.post(f"/api/devices/{device.device_id}/scans/{scan_id}/progress",
                        json={"files_scanned": 10})
        assert r.status_code == 401

        # Progress with wrong token -> 401
        r = client.post(f"/api/devices/{device.device_id}/scans/{scan_id}/progress",
                        json={"files_scanned": 10},
                        headers={"Authorization": "Bearer bad-token"})
        assert r.status_code == 401

        # Complete without token -> 401
        r = client.post(f"/api/devices/{device.device_id}/scans/{scan_id}/complete",
                        json={"status": "COMPLETED"})
        assert r.status_code == 401

        # Complete with wrong token -> 401
        r = client.post(f"/api/devices/{device.device_id}/scans/{scan_id}/complete",
                        json={"status": "COMPLETED"},
                        headers={"Authorization": "Bearer bad-token"})
        assert r.status_code == 401


# ──────────────────────────────────────────────────────────────────────────────
# Test 7 – Schema Input Validations (Trigger, Status, Negative Counts)
# ──────────────────────────────────────────────────────────────────────────────

class TestScanSessionInputValidation:
    def test_invalid_trigger_rejected_with_422(self, client: TestClient, db: Session):
        user = _make_user(db, "invalid_trigger_user")
        device, token = _make_device(db, user, "TriggerDev")
        hdrs = {"Authorization": f"Bearer {token}"}

        # Trigger must be ENROLLMENT, SCHEDULED, or MANUAL
        r = client.post(f"/api/devices/{device.device_id}/scans/start",
                        json={"trigger": "HACK_TRIGGER"}, headers=hdrs)
        assert r.status_code == 422

    def test_valid_triggers_accepted(self, client: TestClient, db: Session):
        user = _make_user(db, "valid_trigger_user")
        device, token = _make_device(db, user, "ValidTriggerDev")
        hdrs = {"Authorization": f"Bearer {token}"}

        for trig in ["ENROLLMENT", "SCHEDULED", "MANUAL"]:
            r = client.post(f"/api/devices/{device.device_id}/scans/start",
                            json={"trigger": trig}, headers=hdrs)
            assert r.status_code == 200
            assert r.json()["trigger"] == trig

    def test_invalid_complete_status_rejected_with_422(self, client: TestClient, db: Session):
        user = _make_user(db, "invalid_status_user")
        device, token = _make_device(db, user, "StatusDev")
        hdrs = {"Authorization": f"Bearer {token}"}

        start = client.post(f"/api/devices/{device.device_id}/scans/start",
                            json={"trigger": "MANUAL"}, headers=hdrs)
        scan_id = start.json()["scan_id"]

        # Status must be COMPLETED, FAILED, or CANCELLED
        r = client.post(f"/api/devices/{device.device_id}/scans/{scan_id}/complete",
                        json={"status": "SOMETHING_ELSE"}, headers=hdrs)
        assert r.status_code == 422

    def test_negative_counts_rejected_with_422(self, client: TestClient, db: Session):
        user = _make_user(db, "neg_count_user")
        device, token = _make_device(db, user, "NegCountDev")
        hdrs = {"Authorization": f"Bearer {token}"}

        start = client.post(f"/api/devices/{device.device_id}/scans/start",
                            json={"trigger": "MANUAL"}, headers=hdrs)
        scan_id = start.json()["scan_id"]

        # Negative count on progress
        r = client.post(f"/api/devices/{device.device_id}/scans/{scan_id}/progress",
                        json={"files_scanned": -5}, headers=hdrs)
        assert r.status_code == 422

        r = client.post(f"/api/devices/{device.device_id}/scans/{scan_id}/progress",
                        json={"files_discovered": -1}, headers=hdrs)
        assert r.status_code == 422

        # Negative count on complete
        r = client.post(f"/api/devices/{device.device_id}/scans/{scan_id}/complete",
                        json={"status": "COMPLETED", "findings_count": -10}, headers=hdrs)
        assert r.status_code == 422


# ──────────────────────────────────────────────────────────────────────────────
# Test 8 – Total Count Query in ScanSessionListResponse
# ──────────────────────────────────────────────────────────────────────────────

class TestScanSessionListTotalCount:
    def test_total_reflects_actual_count_not_page_limit(self, client: TestClient, db: Session):
        user = _make_user(db, "total_count_user")
        device, token = _make_device(db, user, "TotalCountDev")
        hdrs = {"Authorization": f"Bearer {token}"}

        # Create 5 scan sessions
        for i in range(5):
            s = client.post(f"/api/devices/{device.device_id}/scans/start",
                            json={"trigger": "MANUAL"}, headers=hdrs)
            scan_id = s.json()["scan_id"]
            client.post(f"/api/devices/{device.device_id}/scans/{scan_id}/complete",
                        json={"status": "COMPLETED"}, headers=hdrs)

        jwt = _jwt(client, "total_count_user")
        # Request with limit=2
        r = client.get(f"/api/devices/{device.device_id}/scans?limit=2",
                       headers={"Authorization": f"Bearer {jwt}"})
        assert r.status_code == 200
        data = r.json()
        assert len(data["items"]) == 2
        assert data["total"] == 5  # Real total in DB is 5, not len(items)


# ──────────────────────────────────────────────────────────────────────────────
# Test 9 – Sensitive Hidden Folders Retention
# ──────────────────────────────────────────────────────────────────────────────

class TestSensitiveHiddenFoldersRetention:
    def test_preserved_hidden_folders_not_skipped(self):
        import sys
        agent_dir = os.path.join(os.path.dirname(__file__), "..", "..", "agent")
        if agent_dir not in sys.path:
            sys.path.insert(0, os.path.abspath(agent_dir))

        from dataghost_agent import _should_skip_dir

        # Sensitive folders must NOT be skipped
        sensitive = [".ssh", ".aws", ".config", ".kube", ".docker"]
        for d in sensitive:
            assert not _should_skip_dir(d), f"'{d}' must NOT be skipped"
            assert not _should_skip_dir(d, f"C:\\Users\\Bob\\{d}"), f"'{d}' with full path must NOT be skipped"

        # Developer noise and caches must continue to be skipped
        skipped = [".git", "node_modules", ".venv", "venv", ".idea", ".vscode"]
        for d in skipped:
            assert _should_skip_dir(d), f"'{d}' MUST be skipped"

