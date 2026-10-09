"""
DataGhost – FastAPI application entry point.

Run with:
    uvicorn main:app --reload --host 0.0.0.0 --port 8000
"""
import hashlib
import json
import logging
import os
import random
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse

from api.router import router as api_router
from api.scan_routes import router as scan_router
from api.incident_routes import router as incident_router
from auth import get_password_hash
from config import settings
from database import Base, SessionLocal, engine, init_db
from models import Device, Incident, ScanLog, User
from schemas.schemas import HealthResponse
from sqlalchemy import or_

logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(message)s")
logger = logging.getLogger(__name__)

from contextlib import asynccontextmanager

from firebase_auth import initialize_firebase_admin

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing database schema …")
    init_db()

    # Initialize Firebase Admin SDK
    try:
        initialize_firebase_admin()
    except Exception as fb_exc:
        logger.warning("Firebase Admin initialization deferred: %s", fb_exc)

    db = SessionLocal()
    try:
        _seed_admin(db)
        _ensure_classifier()
        if os.environ.get("SEED_DEMO_DATA", "").lower() in ("1", "true", "yes") and db.query(Device).count() == 0:
            logger.info("Seeding demo data …")
            _seed_demo_data(db)
            logger.info("Demo data seeded successfully.")
    finally:
        db.close()
    yield



# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------
app = FastAPI(
    title="DataGhost API",
    version="1.0.0",
    description="AI-Powered Data Loss Prevention and Leakage Detection System",
    lifespan=lifespan,
)

# CORS – allow local development origins, LAN IPs, and Dev Tunnels securely with credentials.
cors_origins = (
    settings.all_cors_origins
    if hasattr(settings, "all_cors_origins")
    else [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "https://inc1.devtunnels.ms",
    ]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=r"^https?:\/\/([a-zA-Z0-9_-]+\.)*(devtunnels\.ms|github\.dev|app\.github\.dev|loca\.lt|ngrok-free\.app|ngrok\.io|vercel\.app|localhost)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Mount all API routes under /api and root routes.
app.include_router(api_router, prefix="/api")
app.include_router(scan_router)
app.include_router(incident_router)


# ---------------------------------------------------------------------------
# Root route → redirect to API docs
# ---------------------------------------------------------------------------
@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs")


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/health", response_model=HealthResponse, tags=["health"])
@app.get("/api/health", response_model=HealthResponse, tags=["health"])
def health():
    return {"status": "ok", "version": "1.0.0"}


# ---------------------------------------------------------------------------
# Android Enterprise DPC APK Serving
# ---------------------------------------------------------------------------
@app.get("/dataghost-agent.apk", tags=["android"])
@app.get("/api/dataghost-agent.apk", tags=["android"])
def download_android_agent_apk():
    """
    Serves the DataGhost Android Enterprise DPC APK for QR code enrollment.
    """
    candidate_paths = [
        os.path.join(os.path.dirname(__file__), "static", "dataghost-agent.apk"),
        os.path.join(os.path.dirname(__file__), "..", "mobile", "android", "app", "build", "outputs", "apk", "debug", "app-debug.apk"),
        os.path.join(os.path.dirname(__file__), "..", "mobile", "android", "app", "build", "outputs", "apk", "release", "app-release.apk"),
    ]
    for path in candidate_paths:
        if os.path.exists(path):
            return FileResponse(
                path=path,
                media_type="application/vnd.android.package-archive",
                filename="dataghost-agent.apk",
            )
    raise HTTPException(
        status_code=404,
        detail="DataGhost Agent APK not found. Please build the Android APK first."
    )




# ---------------------------------------------------------------------------
# Admin user seed
# ---------------------------------------------------------------------------
def _seed_admin(db):
    admin_user = os.environ.get("DEFAULT_ADMIN_USER") or "admin"
    admin_email = os.environ.get("DEFAULT_ADMIN_EMAIL") or "admin@dataghost.local"
    admin_pass = os.environ.get("DEFAULT_ADMIN_PASSWORD") or "dataghost123"

    admin = db.query(User).filter(
        or_(User.username == admin_user, User.email == admin_email)
    ).first()
    if not admin:
        admin = User(
            username=admin_user,
            email=admin_email,
            hashed_password=get_password_hash(admin_pass),
            role="admin",
            is_active=True,
        )
        db.add(admin)
        try:
            db.commit()
            logger.info("Admin user '%s' seeded successfully.", admin_user)
        except Exception:
            db.rollback()

    if db.query(User).filter(User.username == "analyst01").first() is None:
        demo_users = [
            User(username="analyst01", email="analyst01@dataghost.local",
                 hashed_password=get_password_hash("analyst123"), role="analyst", is_active=True),
            User(username="analyst02", email="analyst02@dataghost.local",
                 hashed_password=get_password_hash("analyst123"), role="analyst", is_active=True),
            User(username="viewer01", email="viewer01@dataghost.local",
                 hashed_password=get_password_hash("viewer123"), role="analyst", is_active=False),
        ]
        for u in demo_users:
            db.add(u)
        try:
            db.commit()
            logger.info("Demo users seeded.")
        except Exception:
            db.rollback()



# ---------------------------------------------------------------------------
# Classifier bootstrap
# ---------------------------------------------------------------------------
def _ensure_classifier():
    model_dir = os.path.join(os.path.dirname(__file__), "classifier", "model")
    pipeline_path = os.path.join(model_dir, "classifier_pipeline.joblib")
    if not os.path.exists(pipeline_path):
        logger.info("Classifier model not found – training now (this may take 10-30 s) …")
        try:
            from classifier.train_classifier import train_and_save
            train_and_save(model_dir)
            logger.info("Classifier trained and saved.")
        except Exception as exc:
            logger.warning("Could not train classifier: %s", exc)


# ---------------------------------------------------------------------------
# Demo data seed
# ---------------------------------------------------------------------------

_OS_TYPES = ["Windows", "Windows", "Windows", "Linux", "macOS"]
_CLASSIFICATIONS = ["PUBLIC", "INTERNAL", "CONFIDENTIAL", "RESTRICTED"]
_CLASSIFICATION_WEIGHTS = [0.25, 0.40, 0.25, 0.10]
_SEVERITIES = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
_USERS = [f"employee{i:02d}" for i in range(1, 16)]
_DESTINATIONS = ["INTERNAL", "INTERNAL", "CLOUD", "EXTERNAL", "USB"]

_FILENAMES = [
    "customer_data.xlsx", "employee_records.csv", "financial_report_q1.pdf",
    "api_keys.env", "source_code_backup.zip", "database_export.sql",
    "salary_details.xlsx", "client_contracts.docx", "server_credentials.txt",
    "product_roadmap.pptx", "medical_records.xlsx", "legal_documents.zip",
    "holiday_photos.zip", "project_notes.txt", "onboarding_guide.pdf",
    "internal_memo.docx", "network_config.cfg", "backup_2024.tar.gz",
    "customer_feedback.csv", "quarterly_sales.xlsx", "hr_policy.pdf",
    "dev_secrets.yaml", "deployment_config.json", "audit_trail.log",
    "marketing_plan.pptx", "vendor_list.xlsx", "insurance_claims.csv",
    "system_inventory.csv", "meeting_minutes.docx", "training_data.json",
]

_SAMPLE_FINDINGS = [
    [{"rule_name": "email_address", "rule": "email_address", "severity": "MEDIUM", "matches_count": 15, "sample_match": "u***@example.com", "category": "PII"}],
    [{"rule_name": "pan_card", "rule": "pan_card", "severity": "HIGH", "matches_count": 3, "sample_match": "AB******4F", "category": "PII"},
     {"rule_name": "phone_india", "rule": "phone_india", "severity": "MEDIUM", "matches_count": 8, "sample_match": "98******10", "category": "PII"}],
    [{"rule_name": "api_key_generic", "rule": "api_key_generic", "severity": "CRITICAL", "matches_count": 2, "sample_match": "xK9m****************", "category": "CREDENTIALS"}],
    [{"rule_name": "aws_access_key", "rule": "aws_access_key", "severity": "CRITICAL", "matches_count": 1, "sample_match": "AKIA****************", "category": "CREDENTIALS"}],
    [{"rule_name": "credit_card", "rule": "credit_card", "severity": "HIGH", "matches_count": 5, "sample_match": "45**********0366", "category": "FINANCIAL"},
     {"rule_name": "email_address", "rule": "email_address", "severity": "MEDIUM", "matches_count": 12, "sample_match": "c***@corp.com", "category": "PII"}],
    [{"rule_name": "confidential_marker", "rule": "confidential_marker", "severity": "HIGH", "matches_count": 4, "sample_match": "CONFIDENTIAL", "category": "CORPORATE"}],
    [{"rule_name": "private_key", "rule": "private_key", "severity": "CRITICAL", "matches_count": 1, "sample_match": "----****************", "category": "CREDENTIALS"}],
    [{"rule_name": "password_field", "rule": "password_field", "severity": "HIGH", "matches_count": 3, "sample_match": "pass****************", "category": "CREDENTIALS"}],
    [{"rule_name": "aadhaar", "rule": "aadhaar", "severity": "HIGH", "matches_count": 6, "sample_match": "9876 **** 5670", "category": "PII"}],
    [{"rule_name": "employee_data_marker", "rule": "employee_data_marker", "severity": "HIGH", "matches_count": 2, "sample_match": "salary", "category": "CORPORATE"}],
]


def _rand_timestamp(days_back_max: int = 7) -> datetime:
    now = datetime.now(timezone.utc)
    delta_seconds = random.randint(0, days_back_max * 24 * 3600)
    return now - timedelta(seconds=delta_seconds)


def _seed_demo_data(db):
    random.seed(42)

    # ------------------------------------------------------------------
    # 24 Devices
    # ------------------------------------------------------------------
    device_specs = []
    for i in range(1, 13):
        device_specs.append((f"WORKSTATION-{i:02d}", "Windows"))
    for i in range(1, 7):
        device_specs.append((f"LINUX-SERVER-{i:02d}", "Linux"))
    for i in range(1, 4):
        device_specs.append((f"MACBOOK-{i:02d}", "macOS"))
    for i in range(1, 4):
        device_specs.append((f"LAPTOP-{i:02d}", "Windows"))

    devices = []
    for idx, (name, os_type) in enumerate(device_specs):
        d = Device(
            device_name=name,
            device_id=f"DGD-{idx+1:04d}",
            ip_address=f"192.168.1.{10 + idx}",
            status="ACTIVE",
            last_seen=_rand_timestamp(1),
            os_type=os_type,
            agent_version="1.0.0",
            files_scanned=0,
            incidents_count=0,
        )
        db.add(d)
        devices.append(d)

    db.flush()

    # ------------------------------------------------------------------
    # ~200 ScanLogs per device
    # ------------------------------------------------------------------
    total_scans = 200
    for i in range(total_scans):
        device = random.choice(devices)
        classification = random.choices(
            _CLASSIFICATIONS, weights=_CLASSIFICATION_WEIGHTS
        )[0]
        risk = random.randint(0, 100)
        findings_count = random.randint(0, 8)
        sl = ScanLog(
            timestamp=_rand_timestamp(7),
            filename=random.choice(_FILENAMES),
            file_hash=hashlib.md5(f"scan-{i}".encode()).hexdigest(),
            classification=classification,
            risk_score=risk,
            findings_count=findings_count,
            device_id=device.device_id,
        )
        db.add(sl)
        device.files_scanned = (device.files_scanned or 0) + 1

    # ------------------------------------------------------------------
    # Incidents: 37 BLOCKED, 4 CRITICAL, mix of HIGH/MEDIUM
    # ------------------------------------------------------------------
    _incident_templates = [
        # (classification, risk, severity, action_taken, destination, rec_action, status)
        ("RESTRICTED",    92, "CRITICAL", "BLOCKED",  "EXTERNAL", "BLOCK", "OPEN"),
        ("RESTRICTED",    88, "CRITICAL", "BLOCKED",  "CLOUD",    "BLOCK", "OPEN"),
        ("CONFIDENTIAL",  85, "CRITICAL", "BLOCKED",  "USB",      "BLOCK", "ACKNOWLEDGED"),
        ("RESTRICTED",    91, "CRITICAL", "BLOCKED",  "EXTERNAL", "BLOCK", "OPEN"),
        ("CONFIDENTIAL",  78, "HIGH",     "ALERTED",  "CLOUD",    "ALERT", "OPEN"),
        ("CONFIDENTIAL",  74, "HIGH",     "ALERTED",  "EXTERNAL", "ALERT", "ACKNOWLEDGED"),
        ("CONFIDENTIAL",  72, "HIGH",     "ALERTED",  "CLOUD",    "ALERT", "RESOLVED"),
        ("CONFIDENTIAL",  70, "HIGH",     "ALERTED",  "USB",      "ALERT", "OPEN"),
        ("INTERNAL",      65, "HIGH",     "ALERTED",  "EXTERNAL", "ALERT", "OPEN"),
        ("CONFIDENTIAL",  68, "HIGH",     "ALERTED",  "CLOUD",    "ALERT", "RESOLVED"),
    ]

    incidents_data = []

    for j in range(4):
        incidents_data.append(_incident_templates[j])

    for j in range(33):
        risk = random.randint(30, 79)
        sev = "HIGH" if risk >= 60 else "MEDIUM"
        cls = random.choice(["CONFIDENTIAL", "RESTRICTED", "INTERNAL"])
        dest = random.choice(["CLOUD", "EXTERNAL", "USB"])
        status = random.choice(["OPEN", "OPEN", "ACKNOWLEDGED", "RESOLVED"])
        incidents_data.append((cls, risk, sev, "BLOCKED", dest, "BLOCK" if sev == "CRITICAL" else "ALERT", status))

    for j in range(30):
        risk = random.randint(30, 75)
        sev = "HIGH" if risk >= 60 else "MEDIUM"
        cls = random.choice(["CONFIDENTIAL", "INTERNAL"])
        dest = random.choice(["CLOUD", "EXTERNAL", "INTERNAL"])
        status = random.choice(["OPEN", "ACKNOWLEDGED", "RESOLVED"])
        incidents_data.append((cls, risk, sev, "ALERTED", dest, "ALERT", status))

    for j in range(20):
        risk = random.randint(0, 29)
        status = random.choice(["OPEN", "RESOLVED"])
        incidents_data.append(("INTERNAL", risk, "LOW", "ALLOWED", "INTERNAL", "ALLOW", status))

    year = datetime.now(timezone.utc).year
    for idx, (cls, risk, sev, action_taken, dest, rec_action, inc_status) in enumerate(incidents_data):
        device = random.choice(devices)
        findings = random.choice(_SAMPLE_FINDINGS)
        cats = sorted(list(set(f.get("category", "") for f in findings if f.get("category"))))
        rules = sorted(list(set(f.get("rule", f.get("rule_name", "")) for f in findings if f.get("rule") or f.get("rule_name"))))
        
        inc = Incident(
            incident_id=f"DG-{year}-{idx+1:04d}",
            timestamp=_rand_timestamp(7),
            user=random.choice(_USERS),
            filename=random.choice(_FILENAMES),
            file_hash=hashlib.md5(f"inc-{idx}".encode()).hexdigest(),
            classification=cls,
            confidence=0.95,
            risk_score=risk,
            severity=sev,
            recommended_action=rec_action,
            action_taken=action_taken,
            destination=dest,
            action="TRANSFER" if dest != "INTERNAL" else "READ",
            status=inc_status,
            findings_json=json.dumps(findings),
            categories_json=json.dumps(cats),
            triggered_rules_json=json.dumps(rules),
            device_id=device.device_id,
        )
        db.add(inc)
        if action_taken == "BLOCKED":
            device.incidents_count = (device.incidents_count or 0) + 1

    db.commit()
    logger.info(
        "Seeded: %d devices, %d scan logs, %d incidents.",
        len(devices),
        total_scans,
        len(incidents_data),
    )
