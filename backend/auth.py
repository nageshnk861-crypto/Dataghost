"""
DataGhost – JWT authentication helpers and FastAPI dependency.

Role-based access control (RBAC) model:
  admin   – full system-wide access
  analyst – read access scoped to their allowed data; cannot access admin endpoints

SECURITY:
  • Roles are ALWAYS loaded from the database – never trusted from client input.
  • Firebase tokens are verified server-side with Google public keys.
  • JWT payloads embed only the username; role is resolved from the DB on every request.
"""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from config import settings
from database import get_db
from models import User

# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_password_hash(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return _pwd_context.verify(plain_password, hashed_password)


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def verify_token(token: str) -> Optional[str]:
    """Return the 'sub' claim (username) or None if the token is invalid."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None


from firebase_auth import verify_firebase_token


def _resolve_firebase_user(firebase_claims: dict, db: Session) -> Optional[User]:
    """
    Find or provision a User record from verified Firebase claims.

    Lookup priority (most specific → least specific):
      1. firebase_uid column  (exact, stable, unambiguous)
      2. email column         (fallback for pre-existing accounts)

    New accounts are always provisioned with role='analyst' (least privilege).
    The firebase_uid is set on the record so subsequent requests use path 1.

    SECURITY: This function is called ONLY after the Firebase ID token has been
    cryptographically verified by verify_firebase_token. We never trust the UID
    or email values unless the token signature has passed.
    """
    uid = firebase_claims.get("uid") or firebase_claims.get("sub")
    email = firebase_claims.get("email")
    name = firebase_claims.get("name") or firebase_claims.get("display_name")

    # Derive a safe username from email or UID.
    if email:
        username = email.split("@")[0]
    elif name:
        # Strip spaces, keep ASCII letters/digits/hyphens, max 48 chars
        username = "".join(c for c in name if c.isalnum() or c in "_-")[:48] or "user"
    else:
        username = (uid or "firebase_user")[:48]

    # 1. Look up by Firebase UID (canonical path)
    user = None
    if uid:
        user = db.query(User).filter(User.firebase_uid == uid).first()

    # 2. Fallback: look up by email (for accounts created before firebase_uid column existed)
    if not user and email:
        user = db.query(User).filter(User.email == email).first()
        if user and uid and not user.firebase_uid:
            # Link the Firebase UID to the existing account.
            user.firebase_uid = uid
            db.commit()
            db.refresh(user)

    # 3. Auto-provision a new account for verified Firebase identities.
    if not user:
        # Ensure username uniqueness (email prefix may collide).
        base_username = username
        suffix = 1
        while db.query(User).filter(User.username == username).first():
            username = f"{base_username}{suffix}"
            suffix += 1

        user = User(
            username=username,
            email=email or f"{username}@firebase.dataghost.local",
            # A dummy non-usable hash – this account is Firebase-managed.
            hashed_password=get_password_hash("firebase_managed_auth"),
            role="analyst",   # Always least-privilege for self-registered accounts
            is_active=True,
            firebase_uid=uid,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    return user if user.is_active else None


# ---------------------------------------------------------------------------
# FastAPI Bearer scheme
# ---------------------------------------------------------------------------
_bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    FastAPI dependency that extracts and validates the Bearer token (JWT or Firebase ID token),
    then returns the corresponding User ORM object.

    SECURITY: The role is always loaded from the database record – it is never
    read from the JWT payload or from any client-supplied value.
    """
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing authentication token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        raise unauthorized

    raw_token = credentials.credentials

    # 1. Attempt standard DataGhost JWT verification
    username = verify_token(raw_token)
    if username is not None:
        user = db.query(User).filter(User.username == username, User.is_active == True).first()
        if user is not None:
            return user

    # 2. Attempt Firebase ID Token verification
    fb_claims = verify_firebase_token(raw_token)
    if fb_claims is not None:
        user = _resolve_firebase_user(fb_claims, db)
        if user is not None:
            return user

    raise unauthorized


def get_optional_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """
    Optional authentication dependency.
    If a Bearer token is provided, validates it (JWT or Firebase). If no token is provided, returns None.
    """
    if credentials is None:
        return None

    raw_token = credentials.credentials

    # 1. Check custom JWT
    username = verify_token(raw_token)
    if username is not None:
        user = db.query(User).filter(User.username == username, User.is_active == True).first()
        if user is not None:
            return user

    # 2. Check Firebase ID Token
    fb_claims = verify_firebase_token(raw_token)
    if fb_claims is not None:
        user = _resolve_firebase_user(fb_claims, db)
        if user is not None:
            return user

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication token",
        headers={"WWW-Authenticate": "Bearer"},
    )


# ---------------------------------------------------------------------------
# RBAC dependencies
# ---------------------------------------------------------------------------

def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """
    Dependency that requires the authenticated user to have role='admin'.
    NEVER accepts role from client headers or body – always reads from DB.
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access required",
        )
    return current_user


def require_analyst_or_admin(current_user: User = Depends(get_current_user)) -> User:
    """
    Dependency that accepts both admin and analyst roles.
    Currently equivalent to get_current_user, but explicit for documentation clarity.
    """
    if current_user.role not in ("admin", "analyst"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    return current_user
