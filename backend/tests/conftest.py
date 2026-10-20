import os
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlparse

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import pytest

# Force tests onto an isolated temporary SQLite database before importing database/models
_temp_test_db = os.path.join(tempfile.gettempdir(), "dataghost_test_runner.db")

# Guard against accidental execution against remote/production databases:
# Check os.environ, backend/.env via settings, and the actual SQLAlchemy engine URL
from config import settings
raw_candidate_urls = [
    os.environ.get("DATABASE_URL", ""),
    getattr(settings, "DATABASE_URL", ""),
    getattr(settings, "effective_database_url", ""),
]

# Read .env file directly if present to ensure no production database was loaded
env_file_path = backend_dir / ".env"
if env_file_path.exists():
    try:
        with open(env_file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("DATABASE_URL=") or line.startswith("database_url="):
                    val = line.split("=", 1)[1].strip().strip('"').strip("'")
                    raw_candidate_urls.append(val)
    except Exception:
        pass

for url in raw_candidate_urls:
    if not url:
        continue
    # Allow only sqlite or localhost / 127.0.0.1 / ::1
    parsed = urlparse(url)
    scheme = (parsed.scheme or "").lower()
    hostname = (parsed.hostname or "").lower()

    if "render.com" in hostname or "onrender.com" in hostname:
        pytest.exit(
            f"\n[SAFETY GUARD] DATABASE_URL points to remote Render database ({hostname}). "
            "Tests are strictly forbidden from running against production databases!",
            returncode=1,
        )

    if scheme.startswith("sqlite"):
        continue

    if hostname and hostname not in ("localhost", "127.0.0.1", "::1"):
        pytest.exit(
            f"\n[SAFETY GUARD] DATABASE_URL points to non-local host ({hostname}). "
            "Tests are strictly forbidden from running against remote databases!",
            returncode=1,
        )

# Enforce clean isolated sqlite test database for this session
os.environ["DATABASE_URL"] = f"sqlite:///{_temp_test_db}"
settings.DATABASE_URL = f"sqlite:///{_temp_test_db}"

from sqlalchemy.orm import Session
from database import SessionLocal, init_db


@pytest.fixture(scope="session", autouse=True)
def init_test_db():
    """Initialize test database schema once per test session."""
    init_db()
    yield
    # Cleanup temp db if exists
    try:
        if os.path.exists(_temp_test_db):
            os.remove(_temp_test_db)
    except Exception:
        pass


@pytest.fixture(scope="function")
def db() -> Session:
    """Provide a database session for tests."""
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture(scope="function")
def db_session() -> Session:
    """Alias for db session fixture."""
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture(scope="function")
def client():
    """FastAPI TestClient fixture."""
    from fastapi.testclient import TestClient
    from main import app
    return TestClient(app)


@pytest.fixture(scope="function")
def cleanup_db(db: Session):
    """Clean up test data after each test."""
    yield
    # Rollback any uncommitted transactions
    db.rollback()


# Configure pytest
def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "slow: marks tests as slow running"
    )
