"""
DataGhost – SQLAlchemy ORM models.
Tables: User, Device, Incident, ScanLog, Finding, AuditLog,
        EnrollmentToken, DeviceProvisioning, DeviceIdentity,
        ScanSession.
Compatible with SQLite (dev) and PostgreSQL (prod)."""
from datetime import datetime, timezone
from enum import Enum
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Text, Float, Index, JSON, ForeignKey, event
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
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, server_default="1", index=True)
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
    
    # Device security and remote command coordination
    device_token_hash = Column(String(64), nullable=True, index=True) # SHA-256 hash of device auth token
    auth_token = Column(String(128), nullable=True, index=True)      # Legacy/compat token field
    scan_requested = Column(Boolean, default=False, nullable=False, server_default="0") # Flag set by dashboard to trigger agent scan

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
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
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

    # Simulated / demo data flag — excluded from real summary metrics
    is_simulated = Column(Boolean, default=False, nullable=False, server_default="0")

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
    scan_id = Column(String(64), unique=True, index=True, nullable=True)
    timestamp = Column(DateTime, default=_utc_now, index=True)
    filename = Column(String(512), nullable=True)
    file_hash = Column(String(128), nullable=True)
    classification = Column(String(32), nullable=True)
    risk_score = Column(Integer, default=0)
    findings_count = Column(Integer, default=0)
    device_id = Column(String(64), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    organization_id = Column(String(64), default="default-org", nullable=True)
    status = Column(String(16), default="COMPLETED", nullable=True)  # COMPLETED | FAILED
    file_size = Column(Integer, nullable=True)
    is_simulated = Column(Boolean, default=False, nullable=False, server_default="0")


class Finding(Base):
    """
    Individual DLP finding persisted from the scan pipeline.
    All evidence is redacted before storage – raw secrets are NEVER persisted.
    Deduplication is handled via the `fingerprint` column.
    """
    __tablename__ = "findings"

    id = Column(Integer, primary_key=True, index=True)
    scan_log_id = Column(Integer, ForeignKey("scan_logs.id"), nullable=True, index=True)
    scan_id = Column(String(64), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    organization_id = Column(String(64), default="default-org", nullable=True, index=True)
    device_id = Column(String(64), nullable=True, index=True)

    # File context
    file_name = Column(String(512), nullable=True)
    file_hash = Column(String(128), nullable=True)

    # Detector identification
    detector_id = Column(String(64), nullable=True)
    rule_id = Column(String(128), nullable=True)
    category = Column(String(64), nullable=True, index=True)       # CREDENTIALS | PII | FINANCIAL | CORPORATE
    severity = Column(String(16), default="LOW", index=True)       # LOW | MEDIUM | HIGH | CRITICAL
    confidence = Column(Float, default=1.0)
    risk_score = Column(Integer, default=0)

    # Location in source
    line_number = Column(Integer, default=0)
    column_number = Column(Integer, default=0)
    char_start = Column(Integer, default=0)
    char_end = Column(Integer, default=0)

    # Redacted evidence (NO raw secrets)
    evidence_redacted = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    remediation = Column(Text, nullable=True)

    # Deduplication
    fingerprint = Column(String(64), nullable=True, index=True)

    # Lifecycle
    status = Column(String(16), default="OPEN", index=True)        # OPEN | ACKNOWLEDGED | RESOLVED | FALSE_POSITIVE
    is_simulated = Column(Boolean, default=False, nullable=False, server_default="0")
    first_seen_at = Column(DateTime, default=_utc_now)
    last_seen_at = Column(DateTime, default=_utc_now)
    occurrence_count = Column(Integer, default=1)

    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)

    __table_args__ = (
        Index("ix_findings_fingerprint_device", fingerprint, device_id),
        Index("ix_findings_user_status", user_id, status),
        Index("ix_findings_severity_status", severity, status),
    )


class AuditLog(Base):
    """
    Append-only security audit log.
    Records scan, finding, incident, and auth events.
    No deletion or editing endpoints are exposed.
    Sensitive data (tokens, passwords) is NEVER logged.
    """
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    actor_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    actor_username = Column(String(64), nullable=True)
    organization_id = Column(String(64), default="default-org", nullable=True)

    action = Column(String(64), nullable=False, index=True)         # SCAN_COMPLETED | FINDING_CREATED | INCIDENT_CREATED | FINDING_STATUS_CHANGED | LOGIN_SUCCESS | LOGIN_FAILURE
    resource_type = Column(String(32), nullable=True, index=True)   # SCAN | FINDING | INCIDENT | USER | DEVICE
    resource_id = Column(String(128), nullable=True)
    result = Column(String(16), default="SUCCESS")                  # SUCCESS | FAILURE | DENIED

    ip_address = Column(String(64), nullable=True)
    request_id = Column(String(64), nullable=True)
    metadata_json = Column(Text, nullable=True)                     # JSON string with extra context (no secrets)

    created_at = Column(DateTime, default=_utc_now, index=True)

    __table_args__ = (
        Index("ix_audit_logs_action_created", action, created_at),
    )


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


@event.listens_for(Finding, "load")
def make_finding_datetimes_aware(target, context):
    """Convert naive datetimes to UTC-aware when loading Finding from DB."""
    for attr in ["first_seen_at", "last_seen_at", "created_at", "updated_at"]:
        dt = getattr(target, attr, None)
        if dt and isinstance(dt, datetime) and dt.tzinfo is None:
            setattr(target, attr, dt.replace(tzinfo=timezone.utc))


@event.listens_for(AuditLog, "load")
def make_auditlog_datetimes_aware(target, context):
    """Convert naive datetimes to UTC-aware when loading AuditLog from DB."""
    for attr in ["created_at"]:
        dt = getattr(target, attr, None)
        if dt and isinstance(dt, datetime) and dt.tzinfo is None:
            setattr(target, attr, dt.replace(tzinfo=timezone.utc))


# ═══════════════════════════════════════════════════════════════════════════
# ScanSession – tracks a full-drive agent scan from start to finish
# ═══════════════════════════════════════════════════════════════════════════
class ScanSession(Base):
    """
    Top-level scan lifecycle record created for every full-drive scan:
    - enrollment-triggered  (trigger=ENROLLMENT)
    - scheduled             (trigger=SCHEDULED)
    - dashboard-triggered   (trigger=MANUAL)

    Status transitions:
      RUNNING → COMPLETED | FAILED | CANCELLED
    When the agent goes offline while status is RUNNING the dashboard
    endpoint marks it INTERRUPTED.

    Privacy: no file contents are ever stored here.
    Only aggregate counters and the last folder path are kept.
    """
    __tablename__ = "scan_sessions"

    id = Column(Integer, primary_key=True, index=True)

    # Universally-unique scan identifier returned to the agent
    scan_id = Column(String(64), unique=True, index=True, nullable=False)

    # Device this scan belongs to
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False, index=True)

    # Owner – copied from device.user_id so ownership checks are O(1)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # What caused this scan to start
    trigger = Column(String(16), nullable=False, default="MANUAL")  # ENROLLMENT | SCHEDULED | MANUAL

    # Lifecycle timestamps
    started_at = Column(DateTime, nullable=False, default=_utc_now)
    finished_at = Column(DateTime, nullable=True)

    # Status
    status = Column(
        String(16), nullable=False, default="RUNNING", index=True
    )  # RUNNING | COMPLETED | FAILED | CANCELLED | INTERRUPTED

    # Progress counters (updated periodically while RUNNING)
    files_discovered = Column(Integer, default=0)
    files_scanned = Column(Integer, default=0)
    files_skipped = Column(Integer, default=0)
    findings_count = Column(Integer, default=0)

    # Last folder the agent was scanning (privacy-safe: no file contents)
    current_path = Column(String(1024), nullable=True)

    # Terminal error (if status=FAILED)
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)


@event.listens_for(ScanSession, "load")
def make_scansession_datetimes_aware(target, context):
    """Convert naive datetimes to UTC-aware when loading ScanSession from DB."""
    for attr in ["started_at", "finished_at", "created_at", "updated_at"]:
        dt = getattr(target, attr, None)
        if dt and isinstance(dt, datetime) and dt.tzinfo is None:
            setattr(target, attr, dt.replace(tzinfo=timezone.utc))
