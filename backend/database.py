"""
DataGhost – SQLAlchemy database setup.
Uses a synchronous engine; compatible with both SQLite (dev) and PostgreSQL (prod).
"""
import os
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from config import settings


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------
db_url = getattr(settings, "effective_database_url", settings.DATABASE_URL)
connect_args = {}
if db_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    db_url,
    connect_args=connect_args,
    pool_pre_ping=True,
)

# Enable WAL mode for SQLite so agent and API can read concurrently.
if db_url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _set_wal_mode(dbapi_conn, _connection_record):
        try:
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# ---------------------------------------------------------------------------
# Base class for ORM models
# ---------------------------------------------------------------------------
class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Database initialization & schema migration helper
# ---------------------------------------------------------------------------
def init_db():
    """Create all tables and apply safe non-destructive schema updates."""
    # Import models so Base has all table metadata registered
    import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    # Schema catch-ups are strictly executed on SQLite dev instances;
    # PostgreSQL relies on Alembic migrations.
    is_sqlite = engine.dialect.name == "sqlite" or str(settings.DATABASE_URL).startswith("sqlite")
    if is_sqlite:
        bool_false_default = "0"
        with engine.connect() as conn:
            # 1. Migrate incidents table if needed
            try:
                res = conn.execute(text("PRAGMA table_info(incidents)"))
                existing_cols = {row[1] for row in res.fetchall()}
                if existing_cols:
                    if "status" not in existing_cols:
                        conn.execute(text("ALTER TABLE incidents ADD COLUMN status VARCHAR(16) DEFAULT 'OPEN'"))
                    if "confidence" not in existing_cols:
                        conn.execute(text("ALTER TABLE incidents ADD COLUMN confidence FLOAT DEFAULT 1.0"))
                    if "recommended_action" not in existing_cols:
                        conn.execute(text("ALTER TABLE incidents ADD COLUMN recommended_action VARCHAR(16) DEFAULT 'ALLOW'"))
                    if "action" not in existing_cols:
                        conn.execute(text("ALTER TABLE incidents ADD COLUMN action VARCHAR(32) DEFAULT 'READ'"))
                    if "categories_json" not in existing_cols:
                        conn.execute(text("ALTER TABLE incidents ADD COLUMN categories_json TEXT"))
                    if "triggered_rules_json" not in existing_cols:
                        conn.execute(text("ALTER TABLE incidents ADD COLUMN triggered_rules_json TEXT"))
                    if "created_at" not in existing_cols:
                        conn.execute(text("ALTER TABLE incidents ADD COLUMN created_at DATETIME"))
                    if "updated_at" not in existing_cols:
                        conn.execute(text("ALTER TABLE incidents ADD COLUMN updated_at DATETIME"))
                    if "is_simulated" not in existing_cols:
                        conn.execute(text("ALTER TABLE incidents ADD COLUMN is_simulated BOOLEAN DEFAULT 0"))
                    conn.commit()
            except Exception:
                pass

            # 2. Migrate devices table if needed
            try:
                res_dev = conn.execute(text("PRAGMA table_info(devices)"))
                dev_cols = {row[1] for row in res_dev.fetchall()}
                if dev_cols:
                    if "platform" not in dev_cols:
                        conn.execute(text("ALTER TABLE devices ADD COLUMN platform VARCHAR(32) DEFAULT 'Windows'"))
                    if "os_name" not in dev_cols:
                        conn.execute(text("ALTER TABLE devices ADD COLUMN os_name VARCHAR(64)"))
                    if "os_version" not in dev_cols:
                        conn.execute(text("ALTER TABLE devices ADD COLUMN os_version VARCHAR(64)"))
                    if "architecture" not in dev_cols:
                        conn.execute(text("ALTER TABLE devices ADD COLUMN architecture VARCHAR(32)"))
                    if "hostname" not in dev_cols:
                        conn.execute(text("ALTER TABLE devices ADD COLUMN hostname VARCHAR(128)"))
                    if "enrolled_at" not in dev_cols:
                        conn.execute(text("ALTER TABLE devices ADD COLUMN enrolled_at DATETIME"))
                    if "organization_id" not in dev_cols:
                        conn.execute(text("ALTER TABLE devices ADD COLUMN organization_id VARCHAR(64) DEFAULT 'default-org'"))
                    if "user_id" not in dev_cols:
                        conn.execute(text("ALTER TABLE devices ADD COLUMN user_id VARCHAR(64)"))
                    if "device_metadata" not in dev_cols:
                        conn.execute(text("ALTER TABLE devices ADD COLUMN device_metadata TEXT"))
                    if "created_at" not in dev_cols:
                        conn.execute(text("ALTER TABLE devices ADD COLUMN created_at DATETIME"))
                    if "updated_at" not in dev_cols:
                        conn.execute(text("ALTER TABLE devices ADD COLUMN updated_at DATETIME"))
                    
                    # New enrollment system columns
                    if "public_key_fingerprint" not in dev_cols:
                        conn.execute(text("ALTER TABLE devices ADD COLUMN public_key_fingerprint VARCHAR(64)"))
                    if "attestation_status" not in dev_cols:
                        conn.execute(text("ALTER TABLE devices ADD COLUMN attestation_status VARCHAR(32) DEFAULT 'PENDING'"))
                    if "identity_provided_by" not in dev_cols:
                        conn.execute(text("ALTER TABLE devices ADD COLUMN identity_provided_by VARCHAR(32)"))
                    if "crypto_algorithm" not in dev_cols:
                        conn.execute(text("ALTER TABLE devices ADD COLUMN crypto_algorithm VARCHAR(32) DEFAULT 'RSA-2048'"))
                    if "device_token_hash" not in dev_cols:
                        conn.execute(text("ALTER TABLE devices ADD COLUMN device_token_hash VARCHAR(64)"))
                    if "auth_token" not in dev_cols:
                        conn.execute(text("ALTER TABLE devices ADD COLUMN auth_token VARCHAR(128)"))
                    if "scan_requested" not in dev_cols:
                        conn.execute(text("ALTER TABLE devices ADD COLUMN scan_requested BOOLEAN DEFAULT 0"))

                    # Backfill platform for existing devices
                    conn.execute(text("""
                        UPDATE devices SET platform = 'Windows' 
                        WHERE (platform IS NULL OR platform = '') AND (os_type = 'win32' OR os_type = 'Windows')
                    """))
                    conn.execute(text("""
                        UPDATE devices SET platform = 'Linux' 
                        WHERE (platform IS NULL OR platform = '') AND (os_type = 'linux' OR os_type = 'Linux')
                    """))
                    conn.execute(text("""
                        UPDATE devices SET platform = 'macOS' 
                        WHERE (platform IS NULL OR platform = '') AND (os_type = 'darwin' OR os_type = 'macOS')
                    """))
                    conn.execute(text("""
                        UPDATE devices SET platform = 'Windows' 
                        WHERE platform IS NULL OR platform = ''
                    """))

                    # Backfill user_id for existing devices if NULL or empty
                    conn.execute(text("""
                        UPDATE devices SET user_id = 1 
                        WHERE user_id IS NULL OR user_id = ''
                    """))
                    conn.execute(text("""
                        CREATE INDEX IF NOT EXISTS idx_device_user_id ON devices(user_id)
                    """))
                    conn.commit()
            except Exception:
                pass

            # 3. Migrate users table if needed
            try:
                res_usr = conn.execute(text("PRAGMA table_info(users)"))
                usr_cols = {row[1] for row in res_usr.fetchall()}
                if usr_cols:
                    if "firebase_uid" not in usr_cols:
                        conn.execute(text("ALTER TABLE users ADD COLUMN firebase_uid VARCHAR(128)"))
                    conn.commit()
            except Exception:
                pass

            # 4. Migrate enrollment_tokens table if needed
            try:
                res_tok = conn.execute(text("PRAGMA table_info(enrollment_tokens)"))
                tok_cols = {row[1] for row in res_tok.fetchall()}
                if tok_cols and "user_id" not in tok_cols:
                    conn.execute(text("ALTER TABLE enrollment_tokens ADD COLUMN user_id INTEGER"))
                    conn.commit()
            except Exception:
                pass

            # 5. Migrate scan_logs table – Phase 5 columns
            try:
                res_sl = conn.execute(text("PRAGMA table_info(scan_logs)"))
                sl_cols = {row[1] for row in res_sl.fetchall()}
                if sl_cols:
                    if "scan_id" not in sl_cols:
                        conn.execute(text("ALTER TABLE scan_logs ADD COLUMN scan_id VARCHAR(64)"))
                    if "user_id" not in sl_cols:
                        conn.execute(text("ALTER TABLE scan_logs ADD COLUMN user_id INTEGER"))
                    if "organization_id" not in sl_cols:
                        conn.execute(text("ALTER TABLE scan_logs ADD COLUMN organization_id VARCHAR(64) DEFAULT 'default-org'"))
                    if "status" not in sl_cols:
                        conn.execute(text("ALTER TABLE scan_logs ADD COLUMN status VARCHAR(16) DEFAULT 'COMPLETED'"))
                    if "file_size" not in sl_cols:
                        conn.execute(text("ALTER TABLE scan_logs ADD COLUMN file_size INTEGER"))
                    if "is_simulated" not in sl_cols:
                        conn.execute(text("ALTER TABLE scan_logs ADD COLUMN is_simulated BOOLEAN DEFAULT 0"))
                    conn.commit()
            except Exception:
                pass

            # 6. Migrate findings table – new columns added in agent support phase
            try:
                res_f = conn.execute(text("PRAGMA table_info(findings)"))
                f_cols = {row[1] for row in res_f.fetchall()}
                if f_cols:
                    if "scan_id" not in f_cols:
                        conn.execute(text("ALTER TABLE findings ADD COLUMN scan_id VARCHAR(64)"))
                    if "organization_id" not in f_cols:
                        conn.execute(text("ALTER TABLE findings ADD COLUMN organization_id VARCHAR(64) DEFAULT 'default-org'"))
                    if "device_id" not in f_cols:
                        conn.execute(text("ALTER TABLE findings ADD COLUMN device_id VARCHAR(64)"))
                    if "detector_id" not in f_cols:
                        conn.execute(text("ALTER TABLE findings ADD COLUMN detector_id VARCHAR(64)"))
                    if "rule_id" not in f_cols:
                        conn.execute(text("ALTER TABLE findings ADD COLUMN rule_id VARCHAR(128)"))
                    if "column_number" not in f_cols:
                        conn.execute(text("ALTER TABLE findings ADD COLUMN column_number INTEGER DEFAULT 0"))
                    if "char_start" not in f_cols:
                        conn.execute(text("ALTER TABLE findings ADD COLUMN char_start INTEGER DEFAULT 0"))
                    if "char_end" not in f_cols:
                        conn.execute(text("ALTER TABLE findings ADD COLUMN char_end INTEGER DEFAULT 0"))
                    if "remediation" not in f_cols:
                        conn.execute(text("ALTER TABLE findings ADD COLUMN remediation TEXT"))
                    if "fingerprint" not in f_cols:
                        conn.execute(text("ALTER TABLE findings ADD COLUMN fingerprint VARCHAR(64)"))
                    if "is_simulated" not in f_cols:
                        conn.execute(text("ALTER TABLE findings ADD COLUMN is_simulated BOOLEAN DEFAULT 0"))
                    if "first_seen_at" not in f_cols:
                        conn.execute(text("ALTER TABLE findings ADD COLUMN first_seen_at DATETIME"))
                    if "last_seen_at" not in f_cols:
                        conn.execute(text("ALTER TABLE findings ADD COLUMN last_seen_at DATETIME"))
                    if "occurrence_count" not in f_cols:
                        conn.execute(text("ALTER TABLE findings ADD COLUMN occurrence_count INTEGER DEFAULT 1"))
                    if "updated_at" not in f_cols:
                        conn.execute(text("ALTER TABLE findings ADD COLUMN updated_at DATETIME"))
                    conn.commit()
            except Exception:
                pass

# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------
def get_db():
    """Yield a database session and close it when the request finishes."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
