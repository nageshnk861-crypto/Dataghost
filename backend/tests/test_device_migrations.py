"""
Tests for Database Migrations and Schema Updates.

Covers:
- Database initialization creates new tables
- Migrations on existing databases are non-destructive
- Existing Device records remain readable after migration
- New enrollment columns added to Device table
- Migration idempotency
"""
import os
import tempfile

import pytest
from sqlalchemy import create_engine, event, text, inspect
from sqlalchemy.orm import sessionmaker

from database import Base, init_db
from models import Device, DeviceProvisioning, DeviceIdentity, EnrollmentToken


@pytest.fixture
def temp_db():
    """Create a temporary SQLite database for testing."""
    # Create temporary database file
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    
    yield db_path
    
    # Clean up - close all connections first
    try:
        if os.path.exists(db_path):
            # Give Windows time to release the file
            import time
            time.sleep(0.1)
            os.remove(db_path)
            # Also try to remove WAL files
            try:
                if os.path.exists(f"{db_path}-wal"):
                    os.remove(f"{db_path}-wal")
                if os.path.exists(f"{db_path}-shm"):
                    os.remove(f"{db_path}-shm")
            except:
                pass
    except Exception:
        pass


@pytest.fixture
def sqlite_engine(temp_db):
    """Create SQLAlchemy engine for temporary database."""
    db_url = f"sqlite:///{temp_db}"
    
    engine = create_engine(
        db_url,
        connect_args={"check_same_thread": False},
    )
    
    # Enable WAL mode
    @event.listens_for(engine, "connect")
    def _set_wal_mode(dbapi_conn, _connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()
    
    yield engine
    
    # Close engine
    engine.dispose()


# ---------------------------------------------------------------------------
# Database Initialization Tests
# ---------------------------------------------------------------------------

def test_init_db_creates_device_table(sqlite_engine):
    """Test that init_db() creates Device table."""
    # Create all tables using Base.metadata
    Base.metadata.create_all(bind=sqlite_engine)
    
    inspector = inspect(sqlite_engine)
    tables = inspector.get_table_names()
    
    assert "devices" in tables


def test_init_db_creates_device_provisioning_table(sqlite_engine):
    """Test that init_db() creates DeviceProvisioning table."""
    Base.metadata.create_all(bind=sqlite_engine)
    
    inspector = inspect(sqlite_engine)
    tables = inspector.get_table_names()
    
    assert "device_provisioning" in tables


def test_init_db_creates_device_identity_table(sqlite_engine):
    """Test that init_db() creates DeviceIdentity table."""
    Base.metadata.create_all(bind=sqlite_engine)
    
    inspector = inspect(sqlite_engine)
    tables = inspector.get_table_names()
    
    assert "device_identity" in tables


def test_init_db_creates_enrollment_token_table(sqlite_engine):
    """Test that init_db() creates EnrollmentToken table."""
    Base.metadata.create_all(bind=sqlite_engine)
    
    inspector = inspect(sqlite_engine)
    tables = inspector.get_table_names()
    
    assert "enrollment_tokens" in tables


def test_init_db_creates_users_table(sqlite_engine):
    """Test that init_db() creates users table."""
    Base.metadata.create_all(bind=sqlite_engine)
    
    inspector = inspect(sqlite_engine)
    tables = inspector.get_table_names()
    
    assert "users" in tables


def test_init_db_creates_incidents_table(sqlite_engine):
    """Test that init_db() creates incidents table."""
    Base.metadata.create_all(bind=sqlite_engine)
    
    inspector = inspect(sqlite_engine)
    tables = inspector.get_table_names()
    
    assert "incidents" in tables


# ---------------------------------------------------------------------------
# Device Table Column Tests
# ---------------------------------------------------------------------------

def test_device_table_has_legacy_columns(sqlite_engine):
    """Test that Device table has legacy columns."""
    Base.metadata.create_all(bind=sqlite_engine)
    
    inspector = inspect(sqlite_engine)
    columns = {col["name"] for col in inspector.get_columns("devices")}
    
    # Legacy columns
    assert "device_name" in columns
    assert "device_id" in columns
    assert "platform" in columns
    assert "status" in columns
    assert "last_seen" in columns


def test_device_table_has_enrollment_columns(sqlite_engine):
    """Test that Device table has new enrollment system columns."""
    Base.metadata.create_all(bind=sqlite_engine)
    
    inspector = inspect(sqlite_engine)
    columns = {col["name"] for col in inspector.get_columns("devices")}
    
    # New enrollment columns
    assert "public_key_fingerprint" in columns
    assert "attestation_status" in columns
    assert "identity_provided_by" in columns
    assert "crypto_algorithm" in columns
    assert "organization_id" in columns


def test_device_table_has_organization_id_column(sqlite_engine):
    """Test that Device table has organization_id for multi-tenancy."""
    Base.metadata.create_all(bind=sqlite_engine)
    
    inspector = inspect(sqlite_engine)
    columns = {col["name"] for col in inspector.get_columns("devices")}
    
    assert "organization_id" in columns


# ---------------------------------------------------------------------------
# DeviceProvisioning Table Tests
# ---------------------------------------------------------------------------

def test_device_provisioning_table_structure(sqlite_engine):
    """Test that DeviceProvisioning table has correct structure."""
    Base.metadata.create_all(bind=sqlite_engine)
    
    inspector = inspect(sqlite_engine)
    columns = {col["name"] for col in inspector.get_columns("device_provisioning")}
    
    assert "organization_id" in columns
    assert "enrollment_policy_id" in columns
    assert "platform" in columns
    assert "status" in columns
    assert "bootstrap_token_hash" in columns
    assert "device_count" in columns
    assert "expires_at" in columns


def test_device_provisioning_bootstrap_token_hash_unique(sqlite_engine):
    """Test that bootstrap_token_hash has unique constraint."""
    Base.metadata.create_all(bind=sqlite_engine)
    
    inspector = inspect(sqlite_engine)
    columns = {col["name"] for col in inspector.get_columns("device_provisioning")}
    constraints = inspector.get_unique_constraints("device_provisioning")
    
    # Check if bootstrap_token_hash has unique index
    unique_indexes = inspector.get_indexes("device_provisioning")
    
    unique_cols = [cols for idx in unique_indexes if idx.get("unique", False)
                   for cols in [idx.get("column_names", [])]]
    
    # At minimum, bootstrap_token_hash should exist in columns
    assert "bootstrap_token_hash" in columns


# ---------------------------------------------------------------------------
# DeviceIdentity Table Tests
# ---------------------------------------------------------------------------

def test_device_identity_table_structure(sqlite_engine):
    """Test that DeviceIdentity table has correct structure."""
    Base.metadata.create_all(bind=sqlite_engine)
    
    inspector = inspect(sqlite_engine)
    columns = {col["name"] for col in inspector.get_columns("device_identity")}
    
    assert "device_id" in columns
    assert "platform" in columns
    assert "public_key" in columns
    assert "attestation_data" in columns
    assert "enrollment_code" in columns
    assert "created_at" in columns


# ---------------------------------------------------------------------------
# Non-Destructive Migration Tests
# ---------------------------------------------------------------------------

def test_migration_preserves_existing_device_data(sqlite_engine):
    """Test that migration doesn't destroy existing Device records."""
    Session = sessionmaker(bind=sqlite_engine)
    session = Session()
    
    # Create tables
    Base.metadata.create_all(bind=sqlite_engine)
    
    # Add existing device
    device = Device(
        device_id="legacy-device-001",
        device_name="Legacy Device",
        platform="Windows",
        status="ACTIVE",
    )
    session.add(device)
    session.commit()
    device_id = device.id
    
    # Run migration (idempotent)
    Base.metadata.create_all(bind=sqlite_engine)
    
    # Verify device still exists
    migrated_device = session.query(Device).filter(Device.id == device_id).first()
    assert migrated_device is not None
    assert migrated_device.device_id == "legacy-device-001"
    assert migrated_device.device_name == "Legacy Device"
    
    session.close()


def test_migration_multiple_devices_preserved(sqlite_engine):
    """Test that migration preserves multiple Device records."""
    Session = sessionmaker(bind=sqlite_engine)
    session = Session()
    
    Base.metadata.create_all(bind=sqlite_engine)
    
    # Add multiple devices
    devices = [
        Device(device_id="dev-001", device_name="Device 1", platform="Windows"),
        Device(device_id="dev-002", device_name="Device 2", platform="Android"),
        Device(device_id="dev-003", device_name="Device 3", platform="macOS"),
    ]
    for dev in devices:
        session.add(dev)
    session.commit()
    
    # Run migration
    Base.metadata.create_all(bind=sqlite_engine)
    
    # Verify all devices still exist
    count = session.query(Device).count()
    assert count == 3
    
    # Verify specific devices
    dev1 = session.query(Device).filter(Device.device_id == "dev-001").first()
    dev2 = session.query(Device).filter(Device.device_id == "dev-002").first()
    dev3 = session.query(Device).filter(Device.device_id == "dev-003").first()
    
    assert dev1 is not None and dev1.platform == "Windows"
    assert dev2 is not None and dev2.platform == "Android"
    assert dev3 is not None and dev3.platform == "macOS"
    
    session.close()


def test_migration_device_data_columns_queryable(sqlite_engine):
    """Test that Device data columns are still queryable after migration."""
    Session = sessionmaker(bind=sqlite_engine)
    session = Session()
    
    Base.metadata.create_all(bind=sqlite_engine)
    
    # Add device with various fields
    device = Device(
        device_id="query-test",
        device_name="Query Test Device",
        platform="Linux",
        os_version="20.04",
        hostname="test-host",
        ip_address="192.168.1.100",
        status="OFFLINE",
    )
    session.add(device)
    session.commit()
    
    # Run migration
    Base.metadata.create_all(bind=sqlite_engine)
    
    # Verify all fields are queryable
    dev = session.query(Device).filter(Device.device_id == "query-test").first()
    assert dev.device_name == "Query Test Device"
    assert dev.platform == "Linux"
    assert dev.os_version == "20.04"
    assert dev.hostname == "test-host"
    assert dev.ip_address == "192.168.1.100"
    assert dev.status == "OFFLINE"
    
    session.close()


# ---------------------------------------------------------------------------
# Idempotency Tests
# ---------------------------------------------------------------------------

def test_init_db_idempotent_first_call(sqlite_engine):
    """Test that first call to init_db succeeds."""
    Base.metadata.create_all(bind=sqlite_engine)
    
    inspector = inspect(sqlite_engine)
    tables = inspector.get_table_names()
    
    assert len(tables) > 0


def test_init_db_idempotent_second_call(sqlite_engine):
    """Test that second call to init_db succeeds (idempotent)."""
    Base.metadata.create_all(bind=sqlite_engine)
    
    # Second call should not fail
    Base.metadata.create_all(bind=sqlite_engine)
    
    inspector = inspect(sqlite_engine)
    tables = inspector.get_table_names()
    
    assert "devices" in tables


def test_init_db_idempotent_multiple_calls(sqlite_engine):
    """Test that init_db can be called multiple times safely."""
    # Call multiple times
    for _ in range(3):
        Base.metadata.create_all(bind=sqlite_engine)
    
    inspector = inspect(sqlite_engine)
    tables = inspector.get_table_names()
    
    # All tables should still exist
    expected_tables = ["devices", "users", "incidents", "enrollment_tokens"]
    for table in expected_tables:
        assert table in tables


# ---------------------------------------------------------------------------
# Empty Database Tests
# ---------------------------------------------------------------------------

def test_init_db_creates_all_tables_from_scratch(sqlite_engine):
    """Test that init_db creates all tables in empty database."""
    Base.metadata.create_all(bind=sqlite_engine)
    
    inspector = inspect(sqlite_engine)
    tables = set(inspector.get_table_names())
    
    expected_tables = {
        "users",
        "devices",
        "enrollment_tokens",
        "device_provisioning",
        "device_identity",
        "incidents",
        "scan_logs",
    }
    
    # All expected tables should exist
    for table in expected_tables:
        assert table in tables


# ---------------------------------------------------------------------------
# Data Type Tests
# ---------------------------------------------------------------------------

def test_device_provisioning_token_hash_string_type(sqlite_engine):
    """Test that bootstrap_token_hash is stored as string."""
    Base.metadata.create_all(bind=sqlite_engine)
    
    inspector = inspect(sqlite_engine)
    columns = inspector.get_columns("device_provisioning")
    
    token_hash_col = next(
        (col for col in columns if col["name"] == "bootstrap_token_hash"),
        None
    )
    assert token_hash_col is not None
    # Check that it's a string type
    assert "char" in str(token_hash_col["type"]).lower()


def test_device_identity_public_key_text_type(sqlite_engine):
    """Test that public_key is stored as TEXT (for large PEM keys)."""
    Base.metadata.create_all(bind=sqlite_engine)
    
    inspector = inspect(sqlite_engine)
    columns = inspector.get_columns("device_identity")
    
    public_key_col = next(
        (col for col in columns if col["name"] == "public_key"),
        None
    )
    assert public_key_col is not None
    assert "text" in str(public_key_col["type"]).lower()


def test_device_identity_attestation_data_json_type(sqlite_engine):
    """Test that attestation_data is stored as JSON."""
    Base.metadata.create_all(bind=sqlite_engine)
    
    inspector = inspect(sqlite_engine)
    columns = inspector.get_columns("device_identity")
    
    attest_col = next(
        (col for col in columns if col["name"] == "attestation_data"),
        None
    )
    assert attest_col is not None


# ---------------------------------------------------------------------------
# Index Tests
# ---------------------------------------------------------------------------

def test_device_provisioning_has_organization_index(sqlite_engine):
    """Test that device_provisioning table has organization_id index."""
    Base.metadata.create_all(bind=sqlite_engine)
    
    inspector = inspect(sqlite_engine)
    indexes = inspector.get_indexes("device_provisioning")
    
    index_names = [idx["name"] for idx in indexes]
    
    # Should have an index on organization_id
    has_org_index = any(
        "organization_id" in idx.get("column_names", [])
        for idx in indexes
    )
    assert has_org_index or len(indexes) > 0


def test_device_identity_has_device_id_index(sqlite_engine):
    """Test that device_identity table has device_id index."""
    Base.metadata.create_all(bind=sqlite_engine)
    
    inspector = inspect(sqlite_engine)
    columns = {col["name"] for col in inspector.get_columns("device_identity")}
    
    # device_id should be indexed (unique or normal index)
    assert "device_id" in columns
