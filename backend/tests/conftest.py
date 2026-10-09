"""
Shared pytest fixtures and configuration for DataGhost backend tests.
"""
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import pytest
from sqlalchemy.orm import Session

from database import SessionLocal, init_db


@pytest.fixture(scope="session", autouse=True)
def init_test_db():
    """Initialize test database schema once per test session."""
    init_db()
    yield


@pytest.fixture(scope="function")
def db() -> Session:
    """Provide a database session for tests."""
    session = SessionLocal()
    yield session
    session.close()


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
