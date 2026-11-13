"""
Comprehensive tests for idempotent Firebase user resolution, transaction safety,
concurrency handling, and anti-hijacking protections in DataGhost backend.

Covers:
1. First Firebase login creates one user.
2. Second login reuses the same user.
3. Existing username does not cause duplicate creation or failure.
4. Existing Firebase UID resolves correctly.
5. Different Firebase UID cannot hijack an existing account.
6. Concurrent login simulation does not create duplicates and returns the valid user.
7. Existing admin, analyst, and other roles remain unchanged on subsequent logins.
8. Database rollback works properly after an error without poisoning the session.
"""
import concurrent.futures
import pytest
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from database import SessionLocal
from models import User
from auth import _resolve_firebase_user, get_password_hash


@pytest.fixture
def db_session():
    """Provide a clean DB session for each test."""
    session = SessionLocal()
    yield session
    session.close()


def test_first_firebase_login_creates_one_user(db_session: Session):
    """Test 1: First Firebase login creates exactly one user."""
    uid = "fb_test_uid_new_1"
    email = "newuser1@example.com"

    # Cleanup if needed
    db_session.query(User).filter((User.firebase_uid == uid) | (User.email == email)).delete()
    db_session.commit()

    claims = {
        "uid": uid,
        "email": email,
        "email_verified": True,
        "name": "New User One",
    }
    user = _resolve_firebase_user(claims, db_session)

    assert user is not None
    assert user.firebase_uid == uid
    assert user.email == email
    assert user.role == "analyst"  # Least privilege for new accounts
    assert user.is_active is True

    # Verify exactly one record in the database
    count = db_session.query(User).filter(User.firebase_uid == uid).count()
    assert count == 1


def test_second_login_reuses_same_user(db_session: Session):
    """Test 2: Second login with the same Firebase UID reuses the existing user."""
    uid = "fb_test_uid_reuse_2"
    email = "reuseuser2@example.com"

    # Cleanup
    db_session.query(User).filter((User.firebase_uid == uid) | (User.email == email)).delete()
    db_session.commit()

    claims = {
        "uid": uid,
        "email": email,
        "email_verified": True,
        "name": "Reuse User",
    }
    first_user = _resolve_firebase_user(claims, db_session)
    assert first_user is not None
    first_id = first_user.id

    second_user = _resolve_firebase_user(claims, db_session)
    assert second_user is not None
    assert second_user.id == first_id
    assert second_user.firebase_uid == uid

    # Verify no duplicate user was created
    count = db_session.query(User).filter(User.firebase_uid == uid).count()
    assert count == 1


def test_existing_username_does_not_cause_failure_or_duplicate(db_session: Session):
    """Test 3: Existing username collision results in safe unique username generation."""
    existing_username = "alice_colliding"
    # Pre-create local user with that username
    db_session.query(User).filter(User.username == existing_username).delete()
    db_session.commit()

    local_user = User(
        username=existing_username,
        email="alice_local@example.com",
        hashed_password=get_password_hash("LocalPass123!"),
        role="analyst",
        is_active=True,
    )
    db_session.add(local_user)
    db_session.commit()

    # Now a Firebase user logs in with email alice_colliding@otherdomain.com
    uid = "fb_test_uid_alice_collision"
    claims = {
        "uid": uid,
        "email": "alice_colliding@otherdomain.com",
        "email_verified": True,
        "name": "Alice Other",
    }
    new_user = _resolve_firebase_user(claims, db_session)

    assert new_user is not None
    assert new_user.id != local_user.id
    assert new_user.firebase_uid == uid
    # Username should have been safely suffixed to prevent collision
    assert new_user.username != existing_username
    assert new_user.username.startswith("alice_colliding")


def test_existing_firebase_uid_resolves_correctly(db_session: Session):
    """Test 4: Existing Firebase UID resolves cleanly and immediately."""
    uid = "fb_test_uid_direct_resolve"
    username = "direct_resolved_user"

    db_session.query(User).filter(User.firebase_uid == uid).delete()
    db_session.commit()

    existing = User(
        username=username,
        email="direct@example.com",
        hashed_password=get_password_hash("Pass123!"),
        role="analyst",
        is_active=True,
        firebase_uid=uid,
    )
    db_session.add(existing)
    db_session.commit()

    claims = {"uid": uid, "email": "direct@example.com"}
    resolved = _resolve_firebase_user(claims, db_session)

    assert resolved is not None
    assert resolved.id == existing.id
    assert resolved.username == username


def test_different_firebase_uid_cannot_hijack_existing_account(db_session: Session):
    """Test 5: Different Firebase UID cannot hijack an existing user's account."""
    victim_uid = "fb_victim_uid_5"
    victim_email = "victim@company.com"

    db_session.query(User).filter((User.firebase_uid == victim_uid) | (User.email == victim_email)).delete()
    db_session.commit()

    victim_user = User(
        username="victim_user",
        email=victim_email,
        hashed_password=get_password_hash("VictimPass123!"),
        role="admin",  # Victim is an admin!
        is_active=True,
        firebase_uid=victim_uid,
    )
    db_session.add(victim_user)
    db_session.commit()

    # Attacker tries to log in with same email but different Firebase UID
    attacker_uid = "fb_attacker_uid_evil"
    attacker_claims = {
        "uid": attacker_uid,
        "email": victim_email,
        "email_verified": True,
        "name": "Evil Attacker",
    }

    attacker_user = _resolve_firebase_user(attacker_claims, db_session)

    # Attacker MUST NOT get the victim's account
    assert attacker_user is not None
    assert attacker_user.id != victim_user.id
    assert attacker_user.firebase_uid == attacker_uid
    assert attacker_user.role == "analyst"  # Attacker has analyst role, NOT victim's admin role

    # Victim's account must remain untouched
    db_session.refresh(victim_user)
    assert victim_user.firebase_uid == victim_uid
    assert victim_user.role == "admin"


def test_unverified_email_does_not_link_to_existing_account(db_session: Session):
    """Test 5b: Unverified email does not link to existing password-based account."""
    target_email = "unverified_target@company.com"

    db_session.query(User).filter(User.email == target_email).delete()
    db_session.commit()

    local_admin = User(
        username="target_admin",
        email=target_email,
        hashed_password=get_password_hash("AdminPass123!"),
        role="admin",
        is_active=True,
        firebase_uid=None,  # Not yet linked
    )
    db_session.add(local_admin)
    db_session.commit()

    # Attempt login with unverified email
    unverified_uid = "fb_unverified_attacker_uid"
    claims = {
        "uid": unverified_uid,
        "email": target_email,
        "email_verified": False,  # NOT verified!
        "name": "Unverified User",
    }

    resolved = _resolve_firebase_user(claims, db_session)
    assert resolved is not None
    assert resolved.id != local_admin.id
    assert resolved.firebase_uid == unverified_uid

    # Local admin remains unlinked
    db_session.refresh(local_admin)
    assert local_admin.firebase_uid is None


def test_concurrent_login_simulation(db_session: Session):
    """Test 6: Concurrent login requests for the same new user do not create duplicates."""
    concurrent_uid = "fb_concurrent_test_uid_6"
    concurrent_email = "concurrent_user6@example.com"

    db_session.query(User).filter(
        (User.firebase_uid == concurrent_uid) | (User.email == concurrent_email)
    ).delete()
    db_session.commit()

    claims = {
        "uid": concurrent_uid,
        "email": concurrent_email,
        "email_verified": True,
        "name": "Concurrent Test",
    }

    def login_task():
        session = SessionLocal()
        try:
            user = _resolve_firebase_user(claims, session)
            return user.id if user else None
        finally:
            session.close()

    # Run 6 simultaneous logins across thread pool
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        futures = [executor.submit(login_task) for _ in range(6)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    # All threads must return the exact same user ID
    assert len(results) == 6
    assert all(r is not None for r in results)
    assert len(set(results)) == 1, f"Expected 1 unique user ID, got {set(results)}"

    # Exactly one record in database
    count = db_session.query(User).filter(User.firebase_uid == concurrent_uid).count()
    assert count == 1


def test_existing_roles_remain_unchanged(db_session: Session):
    """Test 7: Existing admin and analyst roles remain unchanged on subsequent logins."""
    admin_uid = "fb_admin_preserve_uid_7"
    analyst_uid = "fb_analyst_preserve_uid_7"

    db_session.query(User).filter(User.firebase_uid.in_([admin_uid, analyst_uid])).delete()
    db_session.commit()

    admin = User(
        username="preserved_admin",
        email="admin_preserve@test.local",
        hashed_password=get_password_hash("AdminPass123!"),
        role="admin",
        is_active=True,
        firebase_uid=admin_uid,
    )
    analyst = User(
        username="preserved_analyst",
        email="analyst_preserve@test.local",
        hashed_password=get_password_hash("AnalystPass123!"),
        role="analyst",
        is_active=True,
        firebase_uid=analyst_uid,
    )
    db_session.add_all([admin, analyst])
    db_session.commit()

    # Login again with admin's Firebase claims
    resolved_admin = _resolve_firebase_user({"uid": admin_uid, "email": admin.email}, db_session)
    assert resolved_admin.role == "admin"

    # Login again with analyst's Firebase claims
    resolved_analyst = _resolve_firebase_user({"uid": analyst_uid, "email": analyst.email}, db_session)
    assert resolved_analyst.role == "analyst"


def test_database_rollback_works_after_failure(db_session: Session):
    """Test 8: Database rollback works cleanly after an error without poisoning session."""
    # Attempt an operation that would violate constraints
    dup_user1 = User(
        username="rollback_test_user",
        email="rollback@test.local",
        hashed_password=get_password_hash("Pass123!"),
        role="analyst",
    )
    dup_user2 = User(
        username="rollback_test_user",  # Duplicate username
        email="rollback2@test.local",
        hashed_password=get_password_hash("Pass123!"),
        role="analyst",
    )

    db_session.query(User).filter(User.username == "rollback_test_user").delete()
    db_session.commit()

    db_session.add(dup_user1)
    db_session.commit()

    db_session.add(dup_user2)
    with pytest.raises(IntegrityError):
        db_session.commit()

    # Session is poisoned until rollback
    db_session.rollback()

    # Verify session is healthy and can perform standard queries and transactions
    user_check = db_session.query(User).filter(User.username == "rollback_test_user").first()
    assert user_check is not None
    assert user_check.id == dup_user1.id

