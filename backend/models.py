"""
DataGhost – SQLAlchemy ORM models.
Tables: User, Device, Incident, ScanLog, EnrollmentToken, DeviceProvisioning, DeviceIdentity.
Compatible with SQLite (dev) and PostgreSQL (prod).
"""
from datetime import datetime, timezone
from enum import Enum
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Text, Float, Index, JSON, event
)
from database import Base


def _utc_now():
    return datetime.now(timezone.utc)


class EnrollmentState(str, Enum):
    """
    Enrollment state machine for device provisioning and enrollment.
    
    Success states:
    - NEW: Device record created, awaiting enrollment initiation
    - DISCOVERING_CONFIGURATION: Device discovering organization configuration
    - CONFIGURATION_FOUND: Organization configuration discovered
    - AUTHENTICATING_DEVICE: Device authentication in progress
    - ATTESTING_DEVICE: Device attestation in progress (if supported)
    - REGISTERING_DEVICE: Device registration with server in progress
    - ENROLLED: Device enrolled successfully
    - CONFIGURING_AGENT: Agent configuration download in progress
    - POLICY_DOWNLOADED: DLP policy successfully downloaded
    - ACTIVE: Device protection active and operational
    
    Failure states:
    - CONFIGURATION_NOT_FOUND: Organization/enrollment configuration not found
    - AUTHENTICATION_FAILED: Device authentication failed
    - ATTESTATION_FAILED: Device attestation failed
    - REGISTRATION_FAILED: Device registration failed
    - POLICY_DOWNLOAD_FAILED: Policy download failed
    - NETWORK_ERROR: Network connectivity error during enrollment
    - UNSUPPORTED_PLATFORM: Device platform not supported by enrollment policy
    """
    # Success states
    NEW = "NEW"
    DISCOVERING_CONFIGURATION = "DISCOVERING_CONFIGURATION"
    CONFIGURATION_FOUND = "CONFIGURATION_FOUND"
    AUTHENTICATING_DEVICE = "AUTHENTICATING_DEVICE"
    ATTESTING_DEVICE = "ATTESTING_DEVICE"
    REGISTERING_DEVICE = "REGISTERING_DEVICE"
    ENROLLED = "ENROLLED"
    CONFIGURING_AGENT = "CONFIGURING_AGENT"
    POLICY_DOWNLOADED = "POLICY_DOWNLOADED"
    ACTIVE = "ACTIVE"
    
    # Failure states
    CONFIGURATION_NOT_FOUND = "CONFIGURATION_NOT_FOUND"
    AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED"
    ATTESTATION_FAILED = "ATTESTATION_FAILED"
    REGISTRATION_FAILED = "REGISTRATION_FAILED"
    POLICY_DOWNLOAD_FAILED = "POLICY_DOWNLOAD_FAILED"
    NETWORK_ERROR = "NETWORK_ERROR"
    UNSUPPORTED_PLATFORM = "UNSUPPORTED_PLATFORM"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(32), default="analyst")   # admin | analyst
    is_active = Column(Boolean, default=True)
    # Firebase UID — nullable for legacy password-only accounts.
    # Unique index allows fast lookup by Firebase UID without allowing duplicates.
    firebase_uid = Column(String(128), unique=True, index=True, nullable=True)
    created_at = Column(DateTime, default=_utc_now)


class Device(Base):
    """
    Device enrollment and identity tracking.
    Stores both legacy device records and new enrollment-system device identities.
    """
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)
    device_name = Column(String(128), nullable=False)
    device_id = Column(String(64), unique=True, index=True, nullable=False)
    platform = Column(String(32), default="Windows", nullable=True)  # Windows | Linux | macOS | Android | iOS
    os_name = Column(String(64), nullable=True)
    os_version = Column(String(64), nullable=True)
    architecture = Column(String(32), nullable=True)
    hostname = Column(String(128), nullable=True)
    ip_address = Column(String(64), nullable=True)
    status = Column(String(16), default="ACTIVE", index=True)        # ACTIVE | OFFLINE | DISABLED
    last_seen = Column(DateTime, default=_utc_now)
    enrolled_at = Column(DateTime, default=_utc_now)
    registered_at = Column(DateTime, default=_utc_now)
    organization_id = Column(String(64), default="default-org", nullable=True)
    user_id = Column(String(64), nullable=True)
    device_metadata = Column(Text, nullable=True)                    # JSON string with hardware/client specs
    os_type = Column(String(32), nullable=True)                      # Kept for backward compatibility
    agent_version = Column(String(32), nullable=True)
    files_scanned = Column(Integer, default=0)
    incidents_count = Column(Integer, default=0)
    
    # New enrollment system columns (optional for existing devices)
    public_key_fingerprint = Column(String(64), nullable=True)       # SHA-256 hash of public key
    attestation_status = Column(String(32), default="PENDING")       # PENDING | VALID | INVALID | NOT_SUPPORTED
    identity_provided_by = Column(String(32), nullable=True)         # TPM | KEYSTORE | KEYCHAIN | MANUAL
    crypto_algorithm = Column(String(32), default="RSA-2048")        # RSA-2048 | RSA-4096 | EC-P256
    
    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)


class EnrollmentToken(Base):
    """
    Stores cryptographically hashed, one-time enrollment tokens for endpoint onboarding.
    Raw tokens are never stored plaintext in the database.
    """
    __tablename__ = "enrollment_tokens"

    id = Column(Integer, primary_key=True, index=True)
    token_hash = Column(String(64), unique=True, index=True, nullable=False)
    enrollment_code = Column(String(32), unique=True, index=True, nullable=False) # e.g. DG-8F3A-7B2C
    platform = Column(String(32), nullable=False)                                 # Windows | Linux | macOS | Android | iOS
    organization_id = Column(String(64), default="default-org", nullable=False)
    created_by = Column(String(64), nullable=True)
    expires_at = Column(DateTime, nullable=False, index=True)
    used_at = Column(DateTime, nullable=True)
    status = Column(String(16), default="PENDING", index=True)                    # PENDING | USED | EXPIRED | CANCELLED
    device_id = Column(String(64), nullable=True, index=True)                     # Assigned permanent device ID
    created_at = Column(DateTime, default=_utc_now)


class DeviceProvisioning(Base):
    """
    Bulk device provisioning records created by administrators.
    
    Stores hashed bootstrap tokens (never plaintext) for secure device provisioning.
    Administrators create provisioning records before deploying devices.
    Devices discover their organization and enrollment configuration through
    these records using MDM, enrollment metadata, or device identity.
    
    Bootstrap tokens are:
    - Generated securely (server-side, 32+ bytes entropy)
    - SHA-256 hashed before storage
    - One-time-use with expiration
    - Never transmitted in plaintext or embedded in APK/EXE
    - Provided through secure channels (MDM, certificate, provisioning config)
    """
    __tablename__ = "device_provisioning"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(String(64), nullable=False, index=True)
    enrollment_policy_id = Column(String(64), nullable=False)
    platform = Column(String(32), nullable=False)                     # Windows | Android | macOS | iOS
    status = Column(String(16), default="ACTIVE", index=True)         # ACTIVE | REVOKED | EXPIRED
    provisioning_method = Column(String(32), default="AUTOMATIC_ENROLLMENT")  # AUTOMATIC_ENROLLMENT | QR_ENROLLMENT | MANUAL_CODE
    
    # Bootstrap token: hashed (never plaintext)
    bootstrap_token_hash = Column(String(64), unique=True, index=True, nullable=False)
    
    # Provisioning tracking
    device_count = Column(Integer, default=0)                         # Number of devices using this provisioning
    created_by = Column(String(64), nullable=True)
    expires_at = Column(DateTime, nullable=True)                      # Optional expiration
    last_used_at = Column(DateTime, nullable=True)
    revoked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)
    
    # Indexes for common queries
    __table_args__ = (
        Index("ix_device_provisioning_org_id_status", organization_id, status),
        Index("ix_device_provisioning_platform", platform),
    )


class DeviceIdentity(Base):
    """
    Unique cryptographic device identity and attestation records.
    
    Each enrolled device receives a unique DataGhost device identity in format:
    DG-DEVICE-XXXXXXXX (where XXXXXXXX is hex entropy).
    
    Device identity workflow:
    1. Device generates or receives cryptographic keypair
    2. Public key registered with server during enrollment
    3. Private key stored in OS-secure storage (TPM, Keystore, Keychain)
    4. Server stores public key fingerprint and attestation data
    5. Device proves identity by signing challenges with private key
    
    Attestation (where supported):
    - Android: Device attestation via Android API
    - iOS/macOS: Certificate-based or Secure Enclave identity
    - Windows: TPM-backed attestation
    
    No private keys are ever transmitted to or stored on the server.
    """
    __tablename__ = "device_identity"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String(32), unique=True, index=True, nullable=False)  # Format: DG-DEVICE-XXXXXXXX
    platform = Column(String(32), nullable=False)                              # Windows | Android | macOS | iOS
    
    # Public key (PEM-encoded, never private key)
    public_key = Column(Text, nullable=False)                                  # PEM-encoded public key
    
    # Attestation data (platform-specific)
    attestation_data = Column(JSON, nullable=True)                             # Platform attestation response
    
    # Enrollment code for user-friendly reference
    enrollment_code = Column(String(16), unique=True, index=True, nullable=False)  # Format: DG-XXXX-XXXX
    
    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)
    
    # Indexes for common queries
    __table_args__ = (
        Index("ix_device_identity_platform", platform),
    )


class Incident(Base):
    """
    Security incidents table storing risk events and DLP scan alerts.
    Raw plaintext secrets are never persisted in this model.
    """
    __tablename__ = "incidents"

    id = Column(Integer, primary_key=True, index=True)
    incident_id = Column(String(32), unique=True, index=True, nullable=False)
    timestamp = Column(DateTime, default=_utc_now, index=True)
    user = Column(String(64), nullable=True, index=True)        # user triggering the event
    filename = Column(String(512), nullable=True)
    file_hash = Column(String(128), nullable=True)
    
    # Classification & Risk Metrics
    classification = Column(String(32), nullable=True, index=True) # PUBLIC | INTERNAL | CONFIDENTIAL | RESTRICTED
    confidence = Column(Float, default=1.0)
    risk_score = Column(Integer, default=0, index=True)
    severity = Column(String(16), default="LOW", index=True)       # LOW | MEDIUM | HIGH | CRITICAL
    recommended_action = Column(String(16), default="ALLOW", index=True) # ALLOW | ALERT | BLOCK
    action_taken = Column(String(16), default="ALLOWED")           # ALLOWED | ALERTED | BLOCKED
    
    # Destination & Event Action
    destination = Column(String(32), default="INTERNAL", index=True) # LOCAL | INTERNAL | CLOUD | USB | EXTERNAL
    action = Column(String(32), default="READ")                     # READ | COPY | SHARE | EMAIL | UPLOAD
    
    # Incident Workflow Status (OPEN | ACKNOWLEDGED | RESOLVED)
    status = Column(String(16), default="OPEN", index=True, nullable=False)
    
    # Masked / Sanitized metadata (NO plaintext secrets stored)
    findings_json = Column(Text, nullable=True)         # JSON-serialised list of masked findings
    categories_json = Column(Text, nullable=True)       # JSON-serialised list of detected categories
    triggered_rules_json = Column(Text, nullable=True)  # JSON-serialised list of triggered rules
    
    device_id = Column(String(64), nullable=True, index=True)
    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)


class ScanLog(Base):
    __tablename__ = "scan_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=_utc_now, index=True)
    filename = Column(String(512), nullable=True)
    file_hash = Column(String(128), nullable=True)
    classification = Column(String(32), nullable=True)
    risk_score = Column(Integer, default=0)
    findings_count = Column(Integer, default=0)
    device_id = Column(String(64), nullable=True)


# ═══════════════════════════════════════════════════════════════════════════
# DateTime Timezone Handling
# ═══════════════════════════════════════════════════════════════════════════
# SQLite stores datetimes as naive strings. When loaded from the database,
# they become naive datetime objects. This event listener converts them to
# timezone-aware (UTC) for consistency.
# ═══════════════════════════════════════════════════════════════════════════

@event.listens_for(DeviceProvisioning, "load")
def make_device_provisioning_datetimes_aware(target, context):
    """Convert naive datetimes to UTC-aware when loading DeviceProvisioning from DB."""
    for attr in ["created_at", "updated_at", "expires_at", "last_used_at", "revoked_at"]:
        dt = getattr(target, attr, None)
        if dt and isinstance(dt, datetime) and dt.tzinfo is None:
            setattr(target, attr, dt.replace(tzinfo=timezone.utc))


@event.listens_for(Device, "load")
def make_device_datetimes_aware(target, context):
    """Convert naive datetimes to UTC-aware when loading Device from DB."""
    for attr in ["last_seen", "enrolled_at", "registered_at", "created_at", "updated_at"]:
        dt = getattr(target, attr, None)
        if dt and isinstance(dt, datetime) and dt.tzinfo is None:
            setattr(target, attr, dt.replace(tzinfo=timezone.utc))


@event.listens_for(EnrollmentToken, "load")
def make_enrollment_token_datetimes_aware(target, context):
    """Convert naive datetimes to UTC-aware when loading EnrollmentToken from DB."""
    for attr in ["expires_at", "used_at", "created_at"]:
        dt = getattr(target, attr, None)
        if dt and isinstance(dt, datetime) and dt.tzinfo is None:
            setattr(target, attr, dt.replace(tzinfo=timezone.utc))


@event.listens_for(DeviceIdentity, "load")
def make_device_identity_datetimes_aware(target, context):
    """Convert naive datetimes to UTC-aware when loading DeviceIdentity from DB."""
    for attr in ["created_at", "updated_at"]:
        dt = getattr(target, attr, None)
        if dt and isinstance(dt, datetime) and dt.tzinfo is None:
            setattr(target, attr, dt.replace(tzinfo=timezone.utc))


@event.listens_for(Incident, "load")
def make_incident_datetimes_aware(target, context):
    """Convert naive datetimes to UTC-aware when loading Incident from DB."""
    for attr in ["timestamp", "created_at", "updated_at"]:
        dt = getattr(target, attr, None)
        if dt and isinstance(dt, datetime) and dt.tzinfo is None:
            setattr(target, attr, dt.replace(tzinfo=timezone.utc))


@event.listens_for(ScanLog, "load")
def make_scanlog_datetimes_aware(target, context):
    """Convert naive datetimes to UTC-aware when loading ScanLog from DB."""
    for attr in ["timestamp"]:
        dt = getattr(target, attr, None)
        if dt and isinstance(dt, datetime) and dt.tzinfo is None:
            setattr(target, attr, dt.replace(tzinfo=timezone.utc))


@event.listens_for(User, "load")
def make_user_datetimes_aware(target, context):
    """Convert naive datetimes to UTC-aware when loading User from DB."""
    for attr in ["created_at"]:
        dt = getattr(target, attr, None)
        if dt and isinstance(dt, datetime) and dt.tzinfo is None:
            setattr(target, attr, dt.replace(tzinfo=timezone.utc))
