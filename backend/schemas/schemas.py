"""
DataGhost – Pydantic v2 request/response schemas.
"""
from datetime import datetime
from typing import Optional, List, Dict, Any, Union, Literal
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "1.0.0"


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    role: str


# ---------------------------------------------------------------------------
# Scanner & Findings
# ---------------------------------------------------------------------------
class FindingSchema(BaseModel):
    rule_name: str
    severity: str          # LOW | MEDIUM | HIGH | CRITICAL
    matches_count: int
    sample_match: str      # first match, truncated/masked
    category: str = ""

# Backwards compatibility alias
Finding = FindingSchema


class ScanFinding(BaseModel):
    rule: str
    category: str
    severity: str
    start: Optional[int] = None
    end: Optional[int] = None
    matched_text: str      # Masked sensitive text


class ScanRequest(BaseModel):
    text: str = Field(..., description="Text content to scan")
    filename: str = Field(default="example.txt", description="File name")
    classification: Optional[str] = Field(default=None, description="Optional classification hint: PUBLIC | INTERNAL | CONFIDENTIAL | RESTRICTED")
    destination: Literal["LOCAL", "INTERNAL", "CLOUD", "USB", "EXTERNAL"] = "LOCAL"
    action: Literal["READ", "COPY", "SHARE", "EMAIL", "UPLOAD"] = "READ"
    file_size: Optional[int] = Field(default=None, description="File size hint in bytes")
    file_size_bytes: Optional[int] = Field(default=None, description="Alias for file_size")
    device_id: Optional[str] = Field(default=None, description="Device ID hint")
    user: Optional[str] = Field(default=None, description="User hint")


class ScanResponse(BaseModel):
    scan_id: str = Field(default="", description="Unique scan identifier")
    filename: str
    file_hash: str = Field(default="", description="SHA-256 hash")
    file_size: Optional[int] = Field(default=0, description="File size in bytes")
    bytes_inspected: int = 0
    scan_status: Literal["COMPLETED", "FAILED", "UNSUPPORTED", "TRUNCATED"] = "FAILED"
    error: Optional[str] = None
    is_simulated: bool = False
    findings: List[ScanFinding] = Field(default_factory=list)
    total_findings: int = 0
    classification: str = "INTERNAL"          # PUBLIC | INTERNAL | CONFIDENTIAL | RESTRICTED
    confidence: float = 1.0
    risk_score: int = 0
    severity: str = "LOW"                 # LOW | MEDIUM | HIGH | CRITICAL
    recommended_action: str = "REVIEW"   # never default to ALLOW
    action_taken: str = "NOT_SCANNED"       # never default to ALLOWED
    incident_id: Optional[str] = None
    breakdown: Dict[str, Any] = Field(default_factory=dict)
    timestamp: Optional[str] = Field(default=None, description="ISO timestamp of scan")


# ---------------------------------------------------------------------------
# Incidents
# ---------------------------------------------------------------------------
class IncidentStatusUpdate(BaseModel):
    status: str = Field(..., description="OPEN | ACKNOWLEDGED | RESOLVED")


class IncidentResponse(BaseModel):
    id: Optional[int] = None
    incident_id: str
    timestamp: datetime
    user: Optional[str] = None
    filename: Optional[str] = None
    file_hash: Optional[str] = None
    classification: Optional[str] = None
    confidence: Optional[float] = 1.0
    risk_score: int
    severity: str
    recommended_action: str = "REVIEW"
    action_taken: str = "NOT_SCANNED"
    destination: str = "INTERNAL"
    action: str = "READ"
    status: str = "OPEN"
    is_simulated: bool = False
    categories: List[str] = Field(default_factory=list)
    triggered_rules: List[str] = Field(default_factory=list)
    findings_json: Optional[str] = None
    device_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class IncidentListResponse(BaseModel):
    items: List[IncidentResponse]
    total: int
    page: int
    per_page: int
    pages: int


# ---------------------------------------------------------------------------
# Devices & Enrollment
# ---------------------------------------------------------------------------
class DeviceRegisterRequest(BaseModel):
    device_name: str
    device_id: str
    ip_address: Optional[str] = None
    os_type: Optional[str] = None
    platform: Optional[str] = None
    agent_version: Optional[str] = None
    os_name: Optional[str] = None
    os_version: Optional[str] = None
    architecture: Optional[str] = None
    hostname: Optional[str] = None


class DeviceResponse(BaseModel):
    id: int
    device_name: str
    device_id: str
    platform: Optional[str] = "Windows"
    os_name: Optional[str] = None
    os_version: Optional[str] = None
    architecture: Optional[str] = None
    hostname: Optional[str] = None
    ip_address: Optional[str] = None
    status: str
    last_seen: Optional[datetime] = None
    enrolled_at: Optional[datetime] = None
    registered_at: Optional[datetime] = None
    organization_id: Optional[str] = None
    user_id: Optional[Union[str, int]] = None
    device_metadata: Optional[str] = None
    os_type: Optional[str] = None
    agent_version: Optional[str] = None
    files_scanned: Optional[int] = 0
    incidents_count: Optional[int] = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class EnrollmentCreateRequest(BaseModel):
    platform: str = Field(..., description="Windows | Linux | macOS | Android | iOS")
    organization_id: Optional[str] = None


class EnrollmentCreateResponse(BaseModel):
    enrollment_code: str
    raw_token: str
    platform: str
    qr_data: str
    server_url: str
    expires_at: datetime
    expires_in_seconds: int
    status: str = "PENDING"


class EnrollmentStatusResponse(BaseModel):
    enrollment_code: str
    platform: str
    status: str  # PENDING | USED | EXPIRED | CANCELLED
    device_id: Optional[str] = None
    device_name: Optional[str] = None
    used_at: Optional[datetime] = None
    expires_at: datetime
    is_expired: bool


class EnrollmentRegisterRequest(BaseModel):
    token: Optional[str] = Field(None, description="Raw enrollment token or enrollment code")
    enrollment_code: Optional[str] = Field(None, description="Enrollment code if token not supplied directly")
    device_name: str
    platform: Optional[str] = None
    os_name: Optional[str] = None
    os_version: Optional[str] = None
    architecture: Optional[str] = None
    hostname: Optional[str] = None
    ip_address: Optional[str] = None
    agent_version: Optional[str] = "1.0.0"
    device_metadata: Optional[Dict[str, Any]] = None


class EnrollmentRegisterResponse(BaseModel):
    device_id: str
    device_name: str
    platform: str
    status: str
    auth_token: Optional[str] = None
    heartbeat_interval_seconds: int = 30
    server_time: datetime
    message: str


class DeviceHeartbeatRequest(BaseModel):
    device_id: Optional[str] = None
    timestamp: Optional[datetime] = None
    agent_version: Optional[str] = None
    status: Optional[str] = "ACTIVE"
    ip_address: Optional[str] = None
    files_scanned: Optional[int] = None
    incidents_count: Optional[int] = None
    cpu_usage: Optional[float] = None
    memory_usage: Optional[float] = None
    device_metadata: Optional[Dict[str, Any]] = None


class DeviceHeartbeatResponse(BaseModel):
    status: str = "ok"
    device_id: str
    last_seen: Optional[datetime] = None
    policy_version: str = "1.0"
    ack_timestamp: datetime


class DeviceUpdateRequest(BaseModel):
    device_name: Optional[str] = None
    status: Optional[str] = None  # ACTIVE | DISABLED
    ip_address: Optional[str] = None


class DeviceScanTriggerRequest(BaseModel):
    custom_content: Optional[str] = Field(None, max_length=1_000_000, description="Optional text content to scan (max 1MB)")
    filename: Optional[str] = None
    max_files: int = Field(1000, ge=1, le=5000, description="Max files to scan, bounded 1 to 5000")
    destination: Literal["LOCAL", "INTERNAL", "CLOUD", "USB", "EXTERNAL"] = "EXTERNAL"
    action: Literal["READ", "COPY", "SHARE", "EMAIL", "UPLOAD"] = "UPLOAD"
    file_path: Optional[str] = Field(None, description="Admin-only: path on server to scan")


class DeviceScanSummaryResponse(BaseModel):
    status: Literal["no_data", "success", "error"]
    has_scan_data: bool
    is_simulated: bool = False
    message: Optional[str] = None
    risk_score: Optional[int] = None
    risk_level: Optional[str] = None
    block_level: Optional[str] = None
    sensitive_files: int = 0
    blocked_transfers: int = 0
    critical_incidents: int = 0
    threats_detected: int = 0
    findings_count: int = 0
    user_information_count: int = 0
    ai_model_sharing_count: int = 0
    scanned_files_count: int = 0
    total_bytes_scanned: int = 0
    high_risk_count: int = 0
    scan_results: List[Dict[str, Any]] = Field(default_factory=list)
    device: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    timestamp: Optional[str] = None

    model_config = {"from_attributes": True}


class DeviceDetailResponse(DeviceResponse):
    last_scan: Optional[datetime] = None
    last_incident: Optional[datetime] = None
    policy_status: str = "Enforced"
    recent_incidents: List[IncidentResponse] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
class ThreatItem(BaseModel):
    # Legacy fields kept for any existing consumers
    label: str
    score: int
    severity: str
    # Fields expected by the frontend ThreatFeed component
    incident_id: str = ""
    filename: str = ""
    risk_score: int = 0
    user: str = ""
    timestamp: str = ""
    action_taken: str = ""


class DashboardStats(BaseModel):
    protected_devices: int
    files_scanned: int
    sensitive_files: int
    blocked_transfers: int
    critical_incidents: int
    scope: str = "all"
    recent_threats: List[ThreatItem] = Field(default_factory=list)


class ActivityDataPoint(BaseModel):
    date: str
    scans: int
    sensitive: int
    blocked: int


# ---------------------------------------------------------------------------
# Persisted Findings & Audit Logs (Phase 5)
# ---------------------------------------------------------------------------
class FindingResponse(BaseModel):
    id: int
    scan_log_id: Optional[int] = None
    scan_id: Optional[str] = None
    user_id: Optional[int] = None
    organization_id: Optional[str] = "default-org"
    device_id: Optional[str] = None

    # File context
    file_name: Optional[str] = None
    file_hash: Optional[str] = None

    # Detector identification
    detector_id: Optional[str] = None
    rule_id: Optional[str] = None
    category: Optional[str] = None
    severity: str = "LOW"
    confidence: float = 1.0
    risk_score: int = 0

    # Location in source
    line_number: int = 0
    column_number: int = 0
    char_start: int = 0
    char_end: int = 0

    # Redacted evidence
    evidence_redacted: Optional[str] = None
    description: Optional[str] = None
    remediation: Optional[str] = None

    # Deduplication & Lifecycle
    fingerprint: Optional[str] = None
    status: str = "OPEN"
    is_simulated: bool = False
    first_seen_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None
    occurrence_count: int = 1

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class FindingListResponse(BaseModel):
    items: List[FindingResponse]
    total: int
    page: int
    per_page: int
    pages: int


class FindingStatusUpdate(BaseModel):
    status: str = Field(..., description="OPEN | ACKNOWLEDGED | RESOLVED | FALSE_POSITIVE")
    comment: Optional[str] = None


class FindingStatsResponse(BaseModel):
    total: int = 0
    open: int = 0
    acknowledged: int = 0
    resolved: int = 0
    false_positive: int = 0
    by_severity: Dict[str, int] = Field(default_factory=dict)
    by_category: Dict[str, int] = Field(default_factory=dict)


class AuditLogResponse(BaseModel):
    id: int
    actor_user_id: Optional[int] = None
    actor_username: Optional[str] = None
    organization_id: Optional[str] = "default-org"
    action: str
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    result: str = "SUCCESS"
    ip_address: Optional[str] = None
    request_id: Optional[str] = None
    metadata_json: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class AuditLogListResponse(BaseModel):
    items: List[AuditLogResponse]
    total: int
    page: int
    per_page: int
    pages: int

