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

from main import app  # noqa: F401
