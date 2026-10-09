"""
DataGhost – Vercel Serverless Function entry point.
Exposes the FastAPI application to Vercel's Python runtime.
"""
import os
import sys

# Ensure backend directory is on sys.path for relative imports
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Also add project root so `api.index` can resolve `backend` modules
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from main import app  # noqa: F401
from database import init_db, SessionLocal
from main import _seed_admin, _seed_demo_data
from models import Device

# On Vercel, SQLite lives in /tmp and is ephemeral.
# Always initialise + seed on cold start.
try:
    init_db()
    db = SessionLocal()
    try:
        _seed_admin(db)
        # Always seed demo data on Vercel (ephemeral /tmp DB)
        if db.query(Device).count() == 0:
            _seed_demo_data(db)
    finally:
        db.close()
except Exception:
    pass
