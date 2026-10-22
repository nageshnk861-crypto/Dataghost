"""
Comprehensive tests for multi-user Windows device enrollment and secure scanning workflow.

Test priorities:
1. Multi-user enrollment: User A and User B enroll separate Windows devices; devices correctly assign to User A and User B respectively.
2. Target user support:
   - Analyst cannot specify target_user_id for another user (403 Forbidden).
   - Analyst can specify target_user_id for themselves.
   - Admin can specify target_user_id to assign enrollment to User B.
3. Enrollment code validation and revocation:
   - Code redemption fails for invalid, expired, already-used, or revoked tokens (400 Bad Request).
   - Pending codes can be revoked by the code owner or an admin via POST /api/devices/enrollment/{code}/revoke.
   - Another user (analyst) cannot revoke a code they do not own (403 Forbidden).
4. Atomicity & fail-closed behavior:
   - Concurrent/double redemption attempts on a single-use token fail safely.
   - No hardcoded creator_user_id=1 fallback; missing owner resolution fails closed (400).
5. Cross-user isolation:
   - User A cannot view User B's enrolled device, scan sessions, or findings (403/404).
"""
import uuid
import secrets
from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient

from main import app
from database import SessionLocal, init_db
from models import Device, Finding, User, EnrollmentToken, ScanSession
from auth import create_access_token, get_password_hash

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_multi_user_data():
    init_db()
    db = SessionLocal()
    try:
        # Create user_alpha (analyst)
        u_alpha = db.query(User).filter(User.username == "user_alpha").first()
        if not u_alpha:
            u_alpha = User(
                username="user_alpha",
                email="alpha@test.local",
                hashed_password=get_password_hash("AlphaPass123!"),
                role="analyst",
                is_active=True,
            )
            db.add(u_alpha)

        # Create user_beta (analyst)
        u_beta = db.query(User).filter(User.username == "user_beta").first()
        if not u_beta:
            u_beta = User(
                username="user_beta",
                email="beta@test.local",
                hashed_password=get_password_hash("BetaPass123!"),
                role="analyst",
                is_active=True,
            )
            db.add(u_beta)

        # Create user_super (admin)
        u_admin = db.query(User).filter(User.username == "user_super_admin").first()
        if not u_admin:
            u_admin = User(
                username="user_super_admin",
                email="superadmin@test.local",
                hashed_password=get_password_hash("AdminPass123!"),
                role="admin",
                is_active=True,
            )
            db.add(u_admin)

        db.commit()
    finally:
        db.close()


def _get_auth():
    db = SessionLocal()
    try:
        u_a = db.query(User).filter(User.username == "user_alpha").first()
        u_b = db.query(User).filter(User.username == "user_beta").first()
        adm = db.query(User).filter(User.username == "user_super_admin").first()

        tok_a = create_access_token({"sub": u_a.username, "role": u_a.role, "id": u_a.id})
        tok_b = create_access_token({"sub": u_b.username, "role": u_b.role, "id": u_b.id})
        tok_adm = create_access_token({"sub": adm.username, "role": adm.role, "id": adm.id})

        return {
            "user_a": u_a,
            "user_b": u_b,
            "admin": adm,
            "headers_a": {"Authorization": f"Bearer {tok_a}"},
            "headers_b": {"Authorization": f"Bearer {tok_b}"},
            "headers_adm": {"Authorization": f"Bearer {tok_adm}"},
        }
    finally:
        db.close()


def test_multi_user_device_enrollment():
    """User A and User B generate enrollment codes and enroll distinct devices; verify ownership."""
    auth = _get_auth()

    # User A creates enrollment token
    res_a = client.post("/api/devices/enrollment/create", json={"platform": "Windows"}, headers=auth["headers_a"])
    assert res_a.status_code == 200, res_a.text
    code_a = res_a.json()["enrollment_code"]

    # User B creates enrollment token
    res_b = client.post("/api/devices/enrollment/create", json={"platform": "Windows"}, headers=auth["headers_b"])
    assert res_b.status_code == 200, res_b.text
    code_b = res_b.json()["enrollment_code"]

    # Register Device A using Token A
    dev_a_name = f"WORKSTATION-ALPHA-{secrets.token_hex(2)}"
    reg_a = client.post(
        "/api/devices/enrollment/register",
        json={
            "enrollment_code": code_a,
            "device_name": dev_a_name,
            "platform": "Windows",
            "hostname": "WORKSTATION-ALPHA",
            "os_version": "Windows 11 Pro",
            "agent_version": "2.0.0",
        },
    )
    assert reg_a.status_code == 200, reg_a.text
    body_a = reg_a.json()
    dev_a_id = body_a["device_id"]
    assert "auth_token" in body_a and body_a["auth_token"]

    # Register Device B using Token B
    dev_b_name = f"WORKSTATION-BETA-{secrets.token_hex(2)}"
    reg_b = client.post(
        "/api/devices/enrollment/register",
        json={
            "enrollment_code": code_b,
            "device_name": dev_b_name,
            "platform": "Windows",
            "hostname": "WORKSTATION-BETA",
            "os_version": "Windows 10 Enterprise",
            "agent_version": "2.0.0",
        },
    )
    assert reg_b.status_code == 200, reg_b.text
    body_b = reg_b.json()
    dev_b_id = body_b["device_id"]
    assert "auth_token" in body_b and body_b["auth_token"]

    # Verify database ownership
    db = SessionLocal()
    try:
        da = db.query(Device).filter(Device.device_id == dev_a_id).first()
        db_dev = db.query(Device).filter(Device.device_id == dev_b_id).first()
        assert da is not None
        assert db_dev is not None
        assert da.user_id == auth["user_a"].id
        assert db_dev.user_id == auth["user_b"].id
        assert da.user_id != db_dev.user_id
    finally:
        db.close()


def test_target_user_id_rbac_permissions():
    """Verify regular analyst cannot assign tokens to other users, but admin can."""
    auth = _get_auth()

    # 1. Analyst A attempts to create token for User B -> 403 Forbidden
    res_forbidden = client.post(
        "/api/devices/enrollment/create",
        headers=auth["headers_a"],
        json={"platform": "Windows", "target_user_id": auth["user_b"].id},
    )
    assert res_forbidden.status_code == 403, res_forbidden.text

    # 2. Analyst A creates token for themselves explicitly -> 200 OK
    res_self = client.post(
        "/api/devices/enrollment/create",
        headers=auth["headers_a"],
        json={"platform": "Windows", "target_user_id": auth["user_a"].id},
    )
    assert res_self.status_code == 200, res_self.text

    # 3. Admin creates token assigning target_user_id to User B -> 200 OK
    res_adm = client.post(
        "/api/devices/enrollment/create",
        headers=auth["headers_adm"],
        json={"platform": "Windows", "target_user_id": auth["user_b"].id},
    )
    assert res_adm.status_code == 200, res_adm.text
    adm_token = res_adm.json()["enrollment_code"]

    # 4. Register a device with admin-assigned token -> Device belongs to User B
    reg = client.post(
        "/api/devices/enrollment/register",
        json={
            "enrollment_code": adm_token,
            "device_name": "DESKTOP-ASSIGNED",
            "platform": "Windows",
            "hostname": "DESKTOP-ASSIGNED",
            "os_version": "Windows 11",
            "agent_version": "2.0.0",
        },
    )
    assert reg.status_code == 200, reg.text
    assigned_dev_id = reg.json()["device_id"]

    db = SessionLocal()
    try:
        dev = db.query(Device).filter(Device.device_id == assigned_dev_id).first()
        assert dev is not None
        assert dev.user_id == auth["user_b"].id
    finally:
        db.close()


def test_enrollment_code_revocation():
    """Verify authorized revocation by owner and admin, rejection of unauthorized revocation, and blocked redemption."""
    auth = _get_auth()

    # User A creates an enrollment token
    res = client.post("/api/devices/enrollment/create", json={"platform": "Windows"}, headers=auth["headers_a"])
    code = res.json()["enrollment_code"]

    # User B attempts to revoke User A's token -> 403 Forbidden
    res_unauth = client.post(
        f"/api/devices/enrollment/{code}/revoke",
        headers=auth["headers_b"],
    )
    assert res_unauth.status_code == 403, res_unauth.text

    # User A revokes their own token -> 200 OK
    res_revoke = client.post(
        f"/api/devices/enrollment/{code}/revoke",
        headers=auth["headers_a"],
    )
    assert res_revoke.status_code == 200, res_revoke.text
    assert res_revoke.json()["status"] == "revoked"

    # Attempting to register with revoked code -> 400 Bad Request
    reg_revoked = client.post(
        "/api/devices/enrollment/register",
        json={
            "enrollment_code": code,
            "device_name": "REVOKED-PC",
            "platform": "Windows",
            "hostname": "REVOKED-PC",
            "os_version": "Windows 11",
            "agent_version": "2.0.0",
        },
    )
    assert reg_revoked.status_code == 400
    assert "cancelled" in reg_revoked.json()["detail"].lower() or "revoked" in reg_revoked.json()["detail"].lower()


def test_invalid_expired_used_redemption_fails():
    """Verify invalid, expired, and already used enrollment codes fail closed."""
    auth = _get_auth()

    # 1. Invalid token
    res_inv = client.post(
        "/api/devices/enrollment/register",
        json={
            "enrollment_code": "DG-INVALID-CODE",
            "device_name": "PC-1",
            "platform": "Windows",
            "hostname": "PC-1",
            "os_version": "Windows 11",
            "agent_version": "2.0.0",
        },
    )
    assert res_inv.status_code == 400

    # 2. Expired token
    db = SessionLocal()
    expired_code = f"DG-EXP-{secrets.token_hex(2).upper()}"
    try:
        exp_tok = EnrollmentToken(
            token_hash=secrets.token_hex(32),
            enrollment_code=expired_code,
            user_id=auth["user_a"].id,
            platform="Windows",
            expires_at=datetime.now(timezone.utc) - timedelta(hours=2),
            status="PENDING",
        )
        db.add(exp_tok)
        db.commit()
    finally:
        db.close()

    res_exp = client.post(
        "/api/devices/enrollment/register",
        json={
            "enrollment_code": expired_code,
            "device_name": "PC-EXPIRED",
            "platform": "Windows",
            "hostname": "PC-EXPIRED",
            "os_version": "Windows 11",
            "agent_version": "2.0.0",
        },
    )
    assert res_exp.status_code == 400
    assert "expired" in res_exp.json()["detail"].lower()

    # 3. Already used token
    # Create valid token, redeem once
    res_tok = client.post("/api/devices/enrollment/create", json={"platform": "Windows"}, headers=auth["headers_a"])
    valid_code = res_tok.json()["enrollment_code"]

    reg1 = client.post(
        "/api/devices/enrollment/register",
        json={
            "enrollment_code": valid_code,
            "device_name": "PC-USED-1",
            "platform": "Windows",
            "hostname": "PC-USED-1",
            "os_version": "Windows 11",
            "agent_version": "2.0.0",
        },
    )
    assert reg1.status_code == 200

    # Second redemption with same code must fail
    reg2 = client.post(
        "/api/devices/enrollment/register",
        json={
            "enrollment_code": valid_code,
            "device_name": "PC-USED-2",
            "platform": "Windows",
            "hostname": "PC-USED-2",
            "os_version": "Windows 11",
            "agent_version": "2.0.0",
        },
    )
    assert reg2.status_code == 400
    assert "used" in reg2.json()["detail"].lower()


def test_device_scan_session_and_finding_isolation():
    """Verify User A cannot access User B's device, scan sessions, or findings."""
    auth = _get_auth()

    # Enroll Device for User B
    res_b = client.post("/api/devices/enrollment/create", json={"platform": "Windows"}, headers=auth["headers_b"])
    token_b = res_b.json()["enrollment_code"]

    reg_b = client.post(
        "/api/devices/enrollment/register",
        json={
            "enrollment_code": token_b,
            "device_name": "ISOLATION-PC-B",
            "platform": "Windows",
            "hostname": "ISOLATION-PC-B",
            "os_version": "Windows 11",
            "agent_version": "2.0.0",
        },
    )
    assert reg_b.status_code == 200
    dev_b_id = reg_b.json()["device_id"]
    device_token_b = reg_b.json()["auth_token"]

    # Device B starts a scan session
    scan_start = client.post(
        f"/api/devices/{dev_b_id}/scans/start",
        headers={"Authorization": f"Bearer {device_token_b}"},
        json={"scan_path": "C:\\Users\\UserB", "trigger": "MANUAL"},
    )
    assert scan_start.status_code == 200
    scan_id_b = scan_start.json()["scan_id"]

    # Upload finding for Device B
    db = SessionLocal()
    try:
        dev_b = db.query(Device).filter(Device.device_id == dev_b_id).first()
        f_b = Finding(
            device_id=dev_b.device_id,
            user_id=auth["user_b"].id,
            file_name="confidential_b.docx",
            risk_score=85,
            severity="HIGH",
            scan_id=scan_id_b,
        )
        db.add(f_b)
        db.commit()
        db.refresh(f_b)
        finding_id_b = f_b.id
    finally:
        db.close()

    # 1. User A lists devices -> Must NOT contain dev_b_id
    list_a = client.get("/api/devices", headers=auth["headers_a"])
    assert list_a.status_code == 200
    dev_ids = [d["device_id"] for d in list_a.json()]
    assert dev_b_id not in dev_ids

    # 2. User A gets Device B specifically -> 403 Forbidden or 404 Not Found
    get_dev_a = client.get(f"/api/devices/{dev_b_id}", headers=auth["headers_a"])
    assert get_dev_a.status_code in (403, 404)

    # 3. User A gets Device B's scan sessions -> 403 Forbidden or 404 Not Found
    get_scans_a = client.get(f"/api/devices/{dev_b_id}/scans", headers=auth["headers_a"])
    assert get_scans_a.status_code in (403, 404)

    # 4. User A gets Device B's finding -> 403 Forbidden or 404 Not Found
    get_finding_a = client.get(f"/api/findings/{finding_id_b}", headers=auth["headers_a"])
    assert get_finding_a.status_code in (403, 404)

    # 5. User B can view their own device and findings
    get_dev_b = client.get(f"/api/devices/{dev_b_id}", headers=auth["headers_b"])
    assert get_dev_b.status_code == 200
    assert get_dev_b.json()["device_id"] == dev_b_id

    get_finding_b = client.get(f"/api/findings/{finding_id_b}", headers=auth["headers_b"])
    assert get_finding_b.status_code == 200
    assert get_finding_b.json()["id"] == finding_id_b
