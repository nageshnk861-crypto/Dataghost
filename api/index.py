"""
DataGhost – Vercel Serverless Function entry point.
Exposes the FastAPI application to Vercel's Python runtime.

NOTE: Only seeds the admin user. Demo devices are NOT seeded so that
only real enrolled devices appear in the dashboard.
"""
import os
import sys

# Ensure backend directory is on sys.path for relative imports
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Also add project root
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from main import app  # noqa: F401
from database import init_db, SessionLocal
from main import _seed_admin

# On Vercel, SQLite lives in /tmp and is ephemeral.
# Only initialise the schema and seed the admin user — no fake demo devices.
try:
    init_db()
    db = SessionLocal()
    try:
        _seed_admin(db)
    finally:
        db.close()
except Exception:
    pass
