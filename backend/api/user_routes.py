"""
DataGhost – user management routes.
GET  /users        → list all users (admin only)
GET  /users/{id}   → single user (admin only)
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import List

from auth import get_current_user
from database import get_db
from models import User

router = APIRouter(prefix="/users", tags=["users"])


def _require_admin(current_user: User = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


def _user_out(u: User) -> dict:
    return {
        "id": u.id,
        "username": u.username,
        "email": u.email or "",
        "role": u.role,
        "is_active": u.is_active,
        "created_at": u.created_at.isoformat() if u.created_at else "",
    }


@router.get("", summary="List all users")
def list_users(
    db: Session = Depends(get_db),
    _admin: User = Depends(_require_admin),
):
    """Return all users in the system. Admin-only."""
    users = db.query(User).order_by(User.id).all()
    return [_user_out(u) for u in users]


@router.get("/{user_id}", summary="Get a single user")
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(_require_admin),
):
    """Return a single user by ID. Admin-only."""
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    return _user_out(u)


@router.patch("/{user_id}/toggle", summary="Toggle user active status")
def toggle_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(_require_admin),
):
    """Toggle is_active for a user. Cannot disable yourself."""
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    if u.id == current_admin.id:
        raise HTTPException(status_code=400, detail="Cannot disable your own account")
    u.is_active = not u.is_active
    db.commit()
    db.refresh(u)
    return _user_out(u)


class UserRoleUpdate(BaseModel):
    role: str = Field(..., description="Role: admin | analyst | viewer")


class UserCreateRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    email: str = Field(..., description="User email")
    password: str = Field(..., min_length=6, description="Password")
    role: str = Field("analyst", description="Role: admin | analyst | viewer")


@router.patch("/{user_id}/role", summary="Update user role (admin only)")
def update_user_role(
    user_id: int,
    payload: UserRoleUpdate,
    db: Session = Depends(get_db),
    _admin: User = Depends(_require_admin),
):
    """Assign appropriate roles (admin, analyst, viewer). Admin-only."""
    norm_role = payload.role.strip().lower()
    valid_roles = {"admin", "analyst", "viewer"}
    if norm_role not in valid_roles:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid role '{payload.role}'. Supported roles: {', '.join(sorted(valid_roles))}",
        )
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    u.role = norm_role
    db.commit()
    db.refresh(u)
    return _user_out(u)


@router.post("", summary="Create user account (admin only)")
def create_user(
    payload: UserCreateRequest,
    db: Session = Depends(get_db),
    _admin: User = Depends(_require_admin),
):
    """Create a new user account with assigned role (admin, analyst, viewer)."""
    from auth import get_password_hash
    norm_role = payload.role.strip().lower()
    if norm_role not in {"admin", "analyst", "viewer"}:
        norm_role = "analyst"

    if db.query(User).filter(User.username == payload.username.strip()).first():
        raise HTTPException(status_code=409, detail="Username already exists")
    if db.query(User).filter(User.email == payload.email.strip()).first():
        raise HTTPException(status_code=409, detail="Email already registered")

    new_user = User(
        username=payload.username.strip(),
        email=payload.email.strip(),
        hashed_password=get_password_hash(payload.password),
        role=norm_role,
        is_active=True,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return _user_out(new_user)
