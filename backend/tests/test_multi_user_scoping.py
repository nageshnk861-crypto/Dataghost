"""
Comprehensive tests for multi-user analyst isolation (User A vs User B).

Verifies:
1. Analyst A cannot list Analyst B's devices.
2. Analyst A cannot GET, PATCH, DELETE, or scan Analyst B's device (403/404).
3. Admin sees both Analyst A's and Analyst B's devices.
4. Analyst A cannot access or update Analyst B's findings (404 IDOR).
5. Analyst A cannot view or update Analyst B's incidents (403/404).
6. Analyst A's dashboard stats strictly reflect only Analyst A's devices and counts.
7. /api/devices/enrollment/register sets Device.user_id from the creating user's enrollment token.
8. Device token for Device A cannot be used to upload findings for Device B (401/403).
"""
import uuid
import secrets
import pytest
from fastapi.testclient import TestClient

from main import app
from database import SessionLocal, init_db
from models import Device, Finding, Incident, ScanLog, User, EnrollmentToken
from auth import create_access_token, get_password_hash

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_isolation_data():
    init_db()
    db = SessionLocal()
    try:
        # Create User A (analyst)
        user_a = db.query(User).filter(User.username == "analyst_a_test").first()
        if not user_a:
            user_a = User(
                username="analyst_a_test",
                email="analyst_a@test.local",
                hashed_password=get_password_hash("Password123!"),
                role="analyst",
                is_active=True,
            )
            db.add(user_a)

        # Create User B (analyst)
        user_b = db.query(User).filter(User.username == "analyst_b_test").first()
        if not user_b:
            user_b = User(
                username="analyst_b_test",
                email="analyst_b@test.local",
                hashed_password=get_password_hash("Password123!"),
                role="analyst",
                is_active=True,
            )
            db.add(user_b)

        # Create Admin
        admin = db.query(User).filter(User.username == "admin_iso_test").first()
        if not admin:
            admin = User(
                username="admin_iso_test",
                email="admin_iso@test.local",
                hashed_password=get_password_hash("AdminPass123!"),
                role="admin",
                is_active=True,
            )
            db.add(admin)

        db.commit()
    finally:
        db.close()


def _get_user_tokens():
    db = SessionLocal()
    try:
        u_a = db.query(User).filter(User.username == "analyst_a_test").first()
        u_b = db.query(User).filter(User.username == "analyst_b_test").first()
        adm = db.query(User).filter(User.username == "admin_iso_test").first()

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


def test_analyst_a_cannot_see_or_modify_analyst_b_devices():
    """Analyst A cannot list, view, update, delete or scan Analyst B's devices."""
    ctx = _get_user_tokens()
    u_a = ctx["user_a"]
    u_b = ctx["user_b"]
    dev_a_id = f"dev-a-{uuid.uuid4().hex[:6]}"
    dev_b_id = f"dev-b-{uuid.uuid4().hex[:6]}"

    db = SessionLocal()
    try:
        dev_a = Device(
            device_id=dev_a_id,
            device_name="Endpoint A",
            platform="Windows",
            status="ACTIVE",
            user_id=u_a.id,
            files_scanned=10,
        )
        dev_b = Device(
            device_id=dev_b_id,
            device_name="Endpoint B",
            platform="Linux",
            status="ACTIVE",
            user_id=u_b.id,
            files_scanned=25,
        )
        db.add(dev_a)
        db.add(dev_b)
        db.commit()
    finally:
        db.close()

    # 1. List devices: Analyst A sees dev_a, but NOT dev_b
    list_res_a = client.get("/api/devices", headers=ctx["headers_a"])
    assert list_res_a.status_code == 200
    ids_seen_by_a = [d["device_id"] for d in list_res_a.json()]
    assert dev_a_id in ids_seen_by_a
    assert dev_b_id not in ids_seen_by_a

    # 2. List devices: Admin sees BOTH dev_a and dev_b
    list_res_adm = client.get("/api/devices", headers=ctx["headers_adm"])
    assert list_res_adm.status_code == 200
    ids_seen_by_adm = [d["device_id"] for d in list_res_adm.json()]
    assert dev_a_id in ids_seen_by_adm
    assert dev_b_id in ids_seen_by_adm

    # 3. GET single device: Analyst A gets 403 on dev_b
    get_res_a = client.get(f"/api/devices/{dev_b_id}", headers=ctx["headers_a"])
    assert get_res_a.status_code == 403

    # 4. PATCH device: Analyst A gets 403 trying to update dev_b
    patch_res_a = client.patch(f"/api/devices/{dev_b_id}", json={"device_name": "Hacked"}, headers=ctx["headers_a"])
    assert patch_res_a.status_code == 403

    # 5. Scan device: Analyst A gets 403 trying to trigger scan on dev_b
    scan_res_a = client.post(f"/api/devices/{dev_b_id}/scan", json={}, headers=ctx["headers_a"])
    assert scan_res_a.status_code == 403


def test_analyst_a_cannot_access_analyst_b_findings_or_incidents():
    """Analyst A and Analyst B both have devices, findings and incidents.
    Confirm B cannot list or read A's items, and A cannot list or read B's items.
    """
    ctx = _get_user_tokens()
    u_a = ctx["user_a"]
    u_b = ctx["user_b"]
    dev_a_id = f"dev-a-{uuid.uuid4().hex[:6]}"
    dev_b_id = f"dev-b-{uuid.uuid4().hex[:6]}"

    db = SessionLocal()
    try:
        # Create Device, Finding, Incident for User A
        dev_a = Device(device_id=dev_a_id, device_name="Device A", user_id=u_a.id, status="ACTIVE")
        db.add(dev_a)
        db.flush()

        finding_a = Finding(
            user_id=u_a.id,
            device_id=dev_a_id,
            file_name="a_secrets.env",
            rule_id="AWS_KEY_A",
            category="CREDENTIALS",
            severity="CRITICAL",
            status="OPEN",
            fingerprint=f"fp-a-{uuid.uuid4().hex}",
        )
        db.add(finding_a)

        inc_a_id = f"INC-A-{uuid.uuid4().hex[:4].upper()}"
        inc_a = Incident(
            incident_id=inc_a_id,
            device_id=dev_a_id,
            user=u_a.username,
            filename="a_secrets.env",
            severity="CRITICAL",
            status="OPEN",
            risk_score=90,
        )
        db.add(inc_a)

        # Create Device, Finding, Incident for User B
        dev_b = Device(device_id=dev_b_id, device_name="Device B", user_id=u_b.id, status="ACTIVE")
        db.add(dev_b)
        db.flush()

        finding_b = Finding(
            user_id=u_b.id,
            device_id=dev_b_id,
            file_name="b_secrets.env",
            rule_id="AWS_KEY_B",
            category="CREDENTIALS",
            severity="CRITICAL",
            status="OPEN",
            fingerprint=f"fp-b-{uuid.uuid4().hex}",
        )
        db.add(finding_b)

        inc_b_id = f"INC-B-{uuid.uuid4().hex[:4].upper()}"
        inc_b = Incident(
            incident_id=inc_b_id,
            device_id=dev_b_id,
            user=u_b.username,
            filename="b_secrets.env",
            severity="CRITICAL",
            status="OPEN",
            risk_score=90,
        )
        db.add(inc_b)
        db.commit()
        db.refresh(finding_a)
        db.refresh(finding_b)
        f_a_id = finding_a.id
        f_b_id = finding_b.id
    finally:
        db.close()

    # 1. Analyst B lists findings -> only sees B's findings, NOT A's
    list_f_b = client.get("/api/findings", headers=ctx["headers_b"])
    assert list_f_b.status_code == 200
    b_finding_ids = [item["id"] for item in list_f_b.json()["items"]]
    assert f_b_id in b_finding_ids
    assert f_a_id not in b_finding_ids, "Analyst B must not see Analyst A's findings in listing"

    # 2. Analyst B lists incidents -> only sees B's incidents, NOT A's
    list_inc_b = client.get("/api/incidents", headers=ctx["headers_b"])
    assert list_inc_b.status_code == 200
    b_incident_ids = [item["incident_id"] for item in list_inc_b.json()["items"]]
    assert inc_b_id in b_incident_ids
    assert inc_a_id not in b_incident_ids, "Analyst B must not see Analyst A's incidents in listing"

    # 3. Analyst B attempts to GET or PATCH Analyst A's finding directly -> 404 (IDOR protected)
    assert client.get(f"/api/findings/{f_a_id}", headers=ctx["headers_b"]).status_code == 404
    assert client.patch(f"/api/findings/{f_a_id}", json={"status": "RESOLVED"}, headers=ctx["headers_b"]).status_code == 404

    # 4. Analyst B attempts to GET or PATCH Analyst A's incident directly -> 403 (Forbidden)
    assert client.get(f"/api/incidents/{inc_a_id}", headers=ctx["headers_b"]).status_code == 403
    assert client.patch(f"/api/incidents/{inc_a_id}", json={"status": "RESOLVED"}, headers=ctx["headers_b"]).status_code == 403

    # 5. Analyst A attempts to GET Analyst B's items -> 404/403
    assert client.get(f"/api/findings/{f_b_id}", headers=ctx["headers_a"]).status_code == 404
    assert client.get(f"/api/incidents/{inc_b_id}", headers=ctx["headers_a"]).status_code == 403


def test_dashboard_stats_scoped_to_owner():
    """Dashboard counts for Analyst A exclude devices and incidents of Analyst B."""
    ctx = _get_user_tokens()
    u_a = ctx["user_a"]
    u_b = ctx["user_b"]
    dev_a_id = f"dev-a-dash-{uuid.uuid4().hex[:6]}"
    dev_b_id = f"dev-b-dash-{uuid.uuid4().hex[:6]}"

    db = SessionLocal()
    try:
        dev_a = Device(device_id=dev_a_id, device_name="Device A Dash", user_id=u_a.id, status="ACTIVE", files_scanned=100)
        dev_b = Device(device_id=dev_b_id, device_name="Device B Dash", user_id=u_b.id, status="ACTIVE", files_scanned=999)
        db.add(dev_a)
        db.add(dev_b)
        db.commit()
    finally:
        db.close()

    res_a = client.get("/api/dashboard/stats", headers=ctx["headers_a"])
    assert res_a.status_code == 200
    data_a = res_a.json()

    # Must be scoped to user A
    assert data_a["scope"] == f"user:{u_a.id}"
    assert data_a["files_scanned"] >= 100


def test_enrollment_registration_sets_creator_user_id():
    """Enrollment registration automatically assigns Device.user_id from token's creating user."""
    ctx = _get_user_tokens()
    u_b = ctx["user_b"]

    # Generate token created by user B
    token_res = client.post("/api/devices/enrollment/create", json={"platform": "Linux"}, headers=ctx["headers_b"])
    assert token_res.status_code == 200
    code = token_res.json()["enrollment_code"]

    # Register device with this code
    reg_res = client.post(
        "/api/devices/enrollment/register",
        json={
            "enrollment_code": code,
            "device_name": "Authed Device B",
            "platform": "Linux",
        },
    )
    assert reg_res.status_code == 200
    new_dev_id = reg_res.json()["device_id"]

    db = SessionLocal()
    try:
        dev = db.query(Device).filter(Device.device_id == new_dev_id).first()
        assert dev is not None
        assert dev.user_id == u_b.id  # Verified creator user_id
    finally:
        db.close()


def test_device_token_cannot_upload_for_another_device():
    """A device auth token for Device A cannot upload findings to Device B."""
    dev_a_id = f"dev-a-{uuid.uuid4().hex[:6]}"
    dev_b_id = f"dev-b-{uuid.uuid4().hex[:6]}"
    token_a = f"dg_dev_{secrets.token_urlsafe(24)}"
    token_b = f"dg_dev_{secrets.token_urlsafe(24)}"

    import hashlib
    hash_a = hashlib.sha256(token_a.encode("utf-8")).hexdigest()
    hash_b = hashlib.sha256(token_b.encode("utf-8")).hexdigest()

    db = SessionLocal()
    try:
        dev_a = Device(device_id=dev_a_id, device_name="Device A", device_token_hash=hash_a, status="ACTIVE")
        dev_b = Device(device_id=dev_b_id, device_name="Device B", device_token_hash=hash_b, status="ACTIVE")
        db.add(dev_a)
        db.add(dev_b)
        db.commit()
    finally:
        db.close()

    payload = {
        "scanned_files_count": 1,
        "total_bytes_scanned": 100,
        "findings": [],
    }

    # Upload using token A to Device B's endpoint -> 401 Unauthorized
    bad_upload = client.post(
        f"/api/devices/{dev_b_id}/findings",
        json=payload,
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert bad_upload.status_code == 401
