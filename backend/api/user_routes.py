"""
DataGhost – user management routes.
GET  /users        → list all users (admin only)
GET  /users/{id}   → single user (admin only)
"""
from fastapi import APIRouter, Depends, HTTPException, status
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
