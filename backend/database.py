"""
DataGhost – SQLAlchemy database setup.
Uses a synchronous engine; compatible with both SQLite (dev) and PostgreSQL (prod).
"""
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from config import settings


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
)

# Enable WAL mode for SQLite so agent and API can read concurrently.
if settings.DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _set_wal_mode(dbapi_conn, _connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()


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
    if settings.DATABASE_URL.startswith("sqlite"):
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
