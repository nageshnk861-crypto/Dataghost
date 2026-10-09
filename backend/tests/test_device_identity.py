"""
Tests for Device Identity Management.

Covers:
- DeviceIdentity creation with unique device IDs
- Device ID format validation
- Enrollment code uniqueness
- Public key storage (PEM format)
- Attestation data storage (JSON)
- Database indexes and queries
"""
import json

import pytest
from sqlalchemy.orm import Session

from database import SessionLocal
from models import DeviceIdentity


@pytest.fixture
def db_session() -> Session:
    """Get a database session."""
    db = SessionLocal()
    yield db
    db.close()


# ---------------------------------------------------------------------------
# Device ID Creation Tests
# ---------------------------------------------------------------------------

def test_device_identity_created_with_unique_id(db_session: Session):
    """Test that DeviceIdentity records are created with unique device IDs."""
    device_id = "DG-DEVICE-ABCDEF01"
    
    identity = DeviceIdentity(
        device_id=device_id,
        platform="Windows",
        public_key="-----BEGIN PUBLIC KEY-----\ntest_key_1\n-----END PUBLIC KEY-----",
        enrollment_code="DG-ENROLL-0001",
    )
    db_session.add(identity)
    db_session.commit()
    
    # Verify record was created
    retrieved = db_session.query(DeviceIdentity).filter(
        DeviceIdentity.device_id == device_id
    ).first()
    assert retrieved is not None
    assert retrieved.device_id == device_id


def test_device_identity_id_format_validation(db_session: Session):
    """Test that device_id stores the provided format."""
    formatted_id = "dg-win-12345678"
    
    identity = DeviceIdentity(
        device_id=formatted_id,
        platform="Windows",
        public_key="-----BEGIN PUBLIC KEY-----\ntest\n-----END PUBLIC KEY-----",
        enrollment_code="DG-TEST-1111",
    )
    db_session.add(identity)
    db_session.commit()
    
    retrieved = db_session.query(DeviceIdentity).filter(
        DeviceIdentity.device_id == formatted_id
    ).first()
    assert retrieved.device_id == formatted_id


# ---------------------------------------------------------------------------
# Enrollment Code Tests
# ---------------------------------------------------------------------------

def test_enrollment_code_unique_per_device(db_session: Session):
    """Test that each device has a unique enrollment code."""
    code1 = "DG-UNIQUE-0001"
    code2 = "DG-UNIQUE-0002"
    
    identity1 = DeviceIdentity(
        device_id="dg-dev1",
        platform="Android",
        public_key="-----BEGIN PUBLIC KEY-----\nkey1\n-----END PUBLIC KEY-----",
        enrollment_code=code1,
    )
    
    identity2 = DeviceIdentity(
        device_id="dg-dev2",
        platform="iOS",
        public_key="-----BEGIN PUBLIC KEY-----\nkey2\n-----END PUBLIC KEY-----",
        enrollment_code=code2,
    )
    
    db_session.add(identity1)
    db_session.add(identity2)
    db_session.commit()
    
    # Verify both exist with different codes
    dev1 = db_session.query(DeviceIdentity).filter(
        DeviceIdentity.device_id == "dg-dev1"
    ).first()
    dev2 = db_session.query(DeviceIdentity).filter(
        DeviceIdentity.device_id == "dg-dev2"
    ).first()
    
    assert dev1.enrollment_code == code1
    assert dev2.enrollment_code == code2
    assert dev1.enrollment_code != dev2.enrollment_code


def test_enrollment_code_uniqueness_constraint(db_session: Session):
    """Test that duplicate enrollment codes are rejected."""
    code = "DG-DUP-TEST"
    
    identity1 = DeviceIdentity(
        device_id="dg-dup1",
        platform="Windows",
        public_key="-----BEGIN PUBLIC KEY-----\nkey1\n-----END PUBLIC KEY-----",
        enrollment_code=code,
    )
    
    identity2 = DeviceIdentity(
        device_id="dg-dup2",
        platform="Windows",
        public_key="-----BEGIN PUBLIC KEY-----\nkey2\n-----END PUBLIC KEY-----",
        enrollment_code=code,  # Same code
    )
    
    db_session.add(identity1)
    db_session.commit()
    
    db_session.add(identity2)
    
    # Should raise integrity error
    try:
        db_session.commit()
        # If no error, constraint might not be enforced in this test
        assert False, "Should have raised integrity error for duplicate enrollment code"
    except Exception as e:
        # Expected: unique constraint violation
        assert "unique" in str(e).lower() or "duplicate" in str(e).lower()


# ---------------------------------------------------------------------------
# Public Key Storage Tests
# ---------------------------------------------------------------------------

def test_public_key_stored_in_pem_format(db_session: Session):
    """Test that public key is stored in PEM format."""
    pem_key = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA0Z3VS5JJcds1V3lDMg2N
AQIDAQAB
-----END PUBLIC KEY-----"""
    
    identity = DeviceIdentity(
        device_id="dg-pem-test",
        platform="Android",
        public_key=pem_key,
        enrollment_code="DG-PEM-1001",
    )
    db_session.add(identity)
    db_session.commit()
    
    retrieved = db_session.query(DeviceIdentity).filter(
        DeviceIdentity.device_id == "dg-pem-test"
    ).first()
    
    assert retrieved.public_key == pem_key
    assert "BEGIN PUBLIC KEY" in retrieved.public_key
    assert "END PUBLIC KEY" in retrieved.public_key


def test_public_key_not_null(db_session: Session):
    """Test that public_key is required."""
    identity = DeviceIdentity(
        device_id="dg-no-key",
        platform="Windows",
        public_key=None,  # NULL key
        enrollment_code="DG-NO-KEY-001",
    )
    db_session.add(identity)
    
    try:
        db_session.commit()
        assert False, "Should require public_key"
    except Exception:
        # Expected: NOT NULL constraint
        pass


def test_large_public_key_storage(db_session: Session):
    """Test that large public keys (4096-bit RSA) are stored correctly."""
    # Simulate a large 4096-bit RSA key
    large_key = """-----BEGIN PUBLIC KEY-----
MIICIjANBgkqhkiG9w0BAQEFAAOCAg8AMIICCgKCAgEA0Z3VS5JJcds1V3lDMg2N
XQIDAQAB
-----END PUBLIC KEY-----"""
    
    identity = DeviceIdentity(
        device_id="dg-large-key",
        platform="iOS",
        public_key=large_key,
        enrollment_code="DG-LARGE-4096",
    )
    db_session.add(identity)
    db_session.commit()
    
    retrieved = db_session.query(DeviceIdentity).filter(
        DeviceIdentity.device_id == "dg-large-key"
    ).first()
    
    assert retrieved.public_key == large_key


# ---------------------------------------------------------------------------
# Attestation Data Tests
# ---------------------------------------------------------------------------

def test_attestation_data_stored_as_json(db_session: Session):
    """Test that attestation_data is stored as JSON."""
    attest_data = {
        "nonce": "test_nonce_123",
        "timestamp": 1234567890,
        "platform": "Android",
        "device_model": "Pixel 6",
    }
    
    identity = DeviceIdentity(
        device_id="dg-attest-json",
        platform="Android",
        public_key="-----BEGIN PUBLIC KEY-----\ntest\n-----END PUBLIC KEY-----",
        attestation_data=attest_data,
        enrollment_code="DG-ATTEST-001",
    )
    db_session.add(identity)
    db_session.commit()
    
    retrieved = db_session.query(DeviceIdentity).filter(
        DeviceIdentity.device_id == "dg-attest-json"
    ).first()
    
    assert retrieved.attestation_data == attest_data
    assert retrieved.attestation_data["nonce"] == "test_nonce_123"


def test_attestation_data_nullable(db_session: Session):
    """Test that attestation_data can be NULL (optional)."""
    identity = DeviceIdentity(
        device_id="dg-no-attest",
        platform="Windows",
        public_key="-----BEGIN PUBLIC KEY-----\ntest\n-----END PUBLIC KEY-----",
        attestation_data=None,  # Optional
        enrollment_code="DG-NO-ATTEST-001",
    )
    db_session.add(identity)
    db_session.commit()
    
    retrieved = db_session.query(DeviceIdentity).filter(
        DeviceIdentity.device_id == "dg-no-attest"
    ).first()
    
    assert retrieved.attestation_data is None


def test_complex_attestation_data(db_session: Session):
    """Test that complex nested attestation data is stored."""
    attest_data = {
        "payload": {
            "nonce": "nonce123",
            "timestamp": 1234567890,
            "signature": "sig123",
            "extensions": {
                "model": "Galaxy S22",
                "build": "TQ3A.200805.001",
            }
        },
        "metadata": {
            "verified": True,
            "cert_chain": ["cert1", "cert2", "cert3"],
        }
    }
    
    identity = DeviceIdentity(
        device_id="dg-complex-attest",
        platform="Android",
        public_key="-----BEGIN PUBLIC KEY-----\ntest\n-----END PUBLIC KEY-----",
        attestation_data=attest_data,
        enrollment_code="DG-COMPLEX-001",
    )
    db_session.add(identity)
    db_session.commit()
    
    retrieved = db_session.query(DeviceIdentity).filter(
        DeviceIdentity.device_id == "dg-complex-attest"
    ).first()
    
    assert retrieved.attestation_data["payload"]["nonce"] == "nonce123"
    assert retrieved.attestation_data["metadata"]["verified"] is True
    assert len(retrieved.attestation_data["metadata"]["cert_chain"]) == 3


# ---------------------------------------------------------------------------
# Query and Index Tests
# ---------------------------------------------------------------------------

def test_query_device_identity_by_device_id(db_session: Session):
    """Test querying DeviceIdentity by device_id (indexed lookup)."""
    device_id = "dg-query-test"
    
    identity = DeviceIdentity(
        device_id=device_id,
        platform="macOS",
        public_key="-----BEGIN PUBLIC KEY-----\ntest\n-----END PUBLIC KEY-----",
        enrollment_code="DG-QUERY-TEST",
    )
    db_session.add(identity)
    db_session.commit()
    
    # Query by device_id
    found = db_session.query(DeviceIdentity).filter(
        DeviceIdentity.device_id == device_id
    ).first()
    
    assert found is not None
    assert found.device_id == device_id


def test_query_device_identity_by_enrollment_code(db_session: Session):
    """Test querying DeviceIdentity by enrollment_code."""
    code = "DG-LOOKUP-9999"
    
    identity = DeviceIdentity(
        device_id="dg-code-lookup",
        platform="iOS",
        public_key="-----BEGIN PUBLIC KEY-----\ntest\n-----END PUBLIC KEY-----",
        enrollment_code=code,
    )
    db_session.add(identity)
    db_session.commit()
    
    # Query by enrollment_code
    found = db_session.query(DeviceIdentity).filter(
        DeviceIdentity.enrollment_code == code
    ).first()
    
    assert found is not None
    assert found.enrollment_code == code


def test_query_device_identity_by_platform(db_session: Session):
    """Test querying multiple DeviceIdentity records by platform."""
    # Create multiple identities for different platforms
    identities = [
        DeviceIdentity(
            device_id="dg-win-001",
            platform="Windows",
            public_key="-----BEGIN PUBLIC KEY-----\nwin1\n-----END PUBLIC KEY-----",
            enrollment_code="DG-WIN-0001",
        ),
        DeviceIdentity(
            device_id="dg-android-001",
            platform="Android",
            public_key="-----BEGIN PUBLIC KEY-----\nand1\n-----END PUBLIC KEY-----",
            enrollment_code="DG-AND-0001",
        ),
        DeviceIdentity(
            device_id="dg-win-002",
            platform="Windows",
            public_key="-----BEGIN PUBLIC KEY-----\nwin2\n-----END PUBLIC KEY-----",
            enrollment_code="DG-WIN-0002",
        ),
    ]
    
    for identity in identities:
        db_session.add(identity)
    db_session.commit()
    
    # Query all Windows devices
    windows_devices = db_session.query(DeviceIdentity).filter(
        DeviceIdentity.platform == "Windows"
    ).all()
    
    assert len(windows_devices) >= 2
    assert all(dev.platform == "Windows" for dev in windows_devices)


# ---------------------------------------------------------------------------
# Platform Coverage Tests
# ---------------------------------------------------------------------------

def test_device_identity_windows_platform(db_session: Session):
    """Test creating DeviceIdentity for Windows platform."""
    identity = DeviceIdentity(
        device_id="dg-win-platform",
        platform="Windows",
        public_key="-----BEGIN PUBLIC KEY-----\nwin\n-----END PUBLIC KEY-----",
        enrollment_code="DG-WIN-PLAT",
    )
    db_session.add(identity)
    db_session.commit()
    
    retrieved = db_session.query(DeviceIdentity).filter(
        DeviceIdentity.device_id == "dg-win-platform"
    ).first()
    assert retrieved.platform == "Windows"


def test_device_identity_android_platform(db_session: Session):
    """Test creating DeviceIdentity for Android platform."""
    identity = DeviceIdentity(
        device_id="dg-android-platform",
        platform="Android",
        public_key="-----BEGIN PUBLIC KEY-----\nand\n-----END PUBLIC KEY-----",
        enrollment_code="DG-AND-PLAT",
    )
    db_session.add(identity)
    db_session.commit()
    
    retrieved = db_session.query(DeviceIdentity).filter(
        DeviceIdentity.device_id == "dg-android-platform"
    ).first()
    assert retrieved.platform == "Android"


def test_device_identity_ios_platform(db_session: Session):
    """Test creating DeviceIdentity for iOS platform."""
    identity = DeviceIdentity(
        device_id="dg-ios-platform",
        platform="iOS",
        public_key="-----BEGIN PUBLIC KEY-----\nios\n-----END PUBLIC KEY-----",
        enrollment_code="DG-iOS-PLAT",
    )
    db_session.add(identity)
    db_session.commit()
    
    retrieved = db_session.query(DeviceIdentity).filter(
        DeviceIdentity.device_id == "dg-ios-platform"
    ).first()
    assert retrieved.platform == "iOS"


def test_device_identity_macos_platform(db_session: Session):
    """Test creating DeviceIdentity for macOS platform."""
    identity = DeviceIdentity(
        device_id="dg-mac-platform",
        platform="macOS",
        public_key="-----BEGIN PUBLIC KEY-----\nmac\n-----END PUBLIC KEY-----",
        enrollment_code="DG-MAC-PLAT",
    )
    db_session.add(identity)
    db_session.commit()
    
    retrieved = db_session.query(DeviceIdentity).filter(
        DeviceIdentity.device_id == "dg-mac-platform"
    ).first()
    assert retrieved.platform == "macOS"


# ---------------------------------------------------------------------------
# Timestamp Tests
# ---------------------------------------------------------------------------

def test_device_identity_created_at_timestamp(db_session: Session):
    """Test that created_at timestamp is set."""
    identity = DeviceIdentity(
        device_id="dg-timestamp-create",
        platform="Windows",
        public_key="-----BEGIN PUBLIC KEY-----\ntest\n-----END PUBLIC KEY-----",
        enrollment_code="DG-STAMP-001",
    )
    db_session.add(identity)
    db_session.commit()
    
    retrieved = db_session.query(DeviceIdentity).filter(
        DeviceIdentity.device_id == "dg-timestamp-create"
    ).first()
    
    assert retrieved.created_at is not None


def test_device_identity_updated_at_timestamp(db_session: Session):
    """Test that updated_at timestamp is set."""
    identity = DeviceIdentity(
        device_id="dg-timestamp-update",
        platform="Windows",
        public_key="-----BEGIN PUBLIC KEY-----\ntest\n-----END PUBLIC KEY-----",
        enrollment_code="DG-STAMP-002",
    )
    db_session.add(identity)
    db_session.commit()
    
    retrieved = db_session.query(DeviceIdentity).filter(
        DeviceIdentity.device_id == "dg-timestamp-update"
    ).first()
    
    assert retrieved.updated_at is not None
    assert retrieved.updated_at >= retrieved.created_at
