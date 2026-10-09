"""
DataGhost – authentication routes.

POST /auth/login          → JWT (username+password against SQLite user table)
GET  /auth/me             → current user info (works with both JWT and Firebase tokens)
POST /auth/register/firebase → sync a verified Firebase account to the DB profile
POST /auth/register       → create a new account with email + password (JWT-only path)

SECURITY:
  • Public registration (both endpoints) ALWAYS assigns role='analyst'.
    Only an admin can promote users via /users/{id} endpoints.
  • Role is ALWAYS read from the database – never from the request body.
  • Passwords are hashed with bcrypt; no plaintext is stored or logged.
  • Firebase tokens are verified server-side before the DB record is created/updated.
"""
import logging
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from auth import (
    create_access_token,
    get_password_hash,
    verify_password,
    get_current_user,
    _resolve_firebase_user,
    require_admin,
)
from database import get_db
from firebase_auth import verify_firebase_token
from models import User
from schemas.schemas import LoginRequest, TokenResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])

# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class FirebaseSyncRequest(BaseModel):
    """Body sent after successful Firebase client-side auth to sync the profile."""
    firebase_id_token: str = Field(..., description="Firebase ID token from client SDK")


class RegisterRequest(BaseModel):
    """Username+password registration (JWT path, no Firebase)."""
    username: str = Field(..., min_length=3, max_length=64)
    email: str = Field(..., description="Email address")
    password: str = Field(..., min_length=8, description="Minimum 8 characters")
    display_name: Optional[str] = Field(None, max_length=128)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_.-]{3,64}$")


def _validate_email(email: str) -> None:
    if not _EMAIL_RE.match(email.strip()):
        raise HTTPException(status_code=422, detail="Invalid email address format.")


def _validate_password(password: str) -> None:
    if len(password) < 8:
        raise HTTPException(status_code=422, detail="Password must be at least 8 characters.")


def _ensure_admin_exists(db: Session) -> None:
    """Ensure a default admin user exists."""
    admin = db.query(User).filter(
        or_(User.username == "admin", User.email == "admin@dataghost.local")
    ).first()
    if not admin:
        admin = User(
            username="admin",
            email="admin@dataghost.local",
            hashed_password=get_password_hash("dataghost123"),
            role="admin",
            is_active=True,
        )
        db.add(admin)
        try:
            db.commit()
        except Exception:
            db.rollback()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """Authenticate via username or email + password and return a JWT access token."""
    _ensure_admin_exists(db)

    identifier = payload.username.strip()
    user = db.query(User).filter(
        or_(User.username == identifier, User.email == identifier)
    ).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        )

    # Role is read from the database – never from the request.
    token = create_access_token({"sub": user.username})
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        username=user.username,
        role=user.role,
    )


@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    """Return the authenticated user's profile. Works with both JWT and Firebase tokens."""
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "role": current_user.role,
        "is_active": current_user.is_active,
        "firebase_uid": current_user.firebase_uid,
    }


@router.post(
    "/register/firebase",
    summary="Sync a Firebase-authenticated account to the application database",
)
def register_via_firebase(
    request: Request,
    body: Optional[FirebaseSyncRequest] = None,
    db: Session = Depends(get_db),
):
    """
    Called by the frontend after a successful Firebase client-side sign-up or sign-in.

    1. Verifies the Firebase ID token server-side (cryptographic check).
    2. Creates or links the application DB profile (role = 'analyst', always).
    3. Returns the application user profile so the frontend can confirm the role.

    Token can be provided in JSON body `{"firebase_id_token": "..."}` or
    via `Authorization: Bearer <token>` header.
    """
    token = body.firebase_id_token if body and body.firebase_id_token else None
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()

    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing Firebase ID token in body or Authorization header.",
        )

    fb_claims = verify_firebase_token(token)
    if not fb_claims:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Firebase token verification failed. The token may be expired or invalid.",
        )

    user = _resolve_firebase_user(fb_claims, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive or could not be provisioned.",
        )

    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "is_active": user.is_active,
        "firebase_uid": user.firebase_uid,
        "message": "Account synchronized successfully.",
    }


@router.post(
    "/register",
    summary="Create a new username+password account (JWT path, no Firebase)",
    status_code=201,
)
def register(
    body: RegisterRequest,
    db: Session = Depends(get_db),
):
    """
    Create a new user account using username + email + password.

    SECURITY:
      • Role is always 'analyst'; clients cannot request 'admin'.
      • Passwords are bcrypt-hashed before storage – never stored in plaintext.
      • Duplicate email and duplicate username return 409 Conflict.
    """
    _validate_email(body.email)
    _validate_password(body.password)

    if not _USERNAME_RE.match(body.username):
        raise HTTPException(
            status_code=422,
            detail="Username must be 3–64 characters and contain only letters, digits, '.', '-', or '_'.",
        )

    # Check for duplicates before inserting.
    existing = db.query(User).filter(
        or_(User.username == body.username.strip(), User.email == body.email.strip().lower())
    ).first()
    if existing:
        if existing.username == body.username.strip():
            raise HTTPException(status_code=409, detail="Username is already taken.")
        raise HTTPException(status_code=409, detail="An account with that email already exists.")

    new_user = User(
        username=body.username.strip(),
        email=body.email.strip().lower(),
        hashed_password=get_password_hash(body.password),
        role="analyst",      # ALWAYS least-privilege; only admin can promote
        is_active=True,
    )
    db.add(new_user)
    try:
        db.commit()
        db.refresh(new_user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="An account with that email or username already exists.")

    token = create_access_token({"sub": new_user.username})
    return {
        "access_token": token,
        "token_type": "bearer",
        "username": new_user.username,
        "email": new_user.email,
        "role": new_user.role,
        "message": "Account created successfully.",
    }


@router.patch(
    "/users/{user_id}/role",
    summary="Promote or demote a user's role (admin only)",
)
def update_user_role(
    user_id: int,
    body: dict,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """
    Change a user's role. Admin only.
    Allowed values: 'admin', 'analyst'.
    Admins cannot demote themselves.
    """
    new_role = (body.get("role") or "").strip().lower()
    if new_role not in ("admin", "analyst"):
        raise HTTPException(status_code=422, detail="Role must be 'admin' or 'analyst'.")

    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="User not found.")
    if u.id == _admin.id and new_role != "admin":
        raise HTTPException(status_code=400, detail="Cannot demote your own admin account.")

    u.role = new_role
    db.commit()
    db.refresh(u)
    return {"id": u.id, "username": u.username, "role": u.role}
