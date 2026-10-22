"""
DataGhost – Database Migration Startup Utility.

Handles safe migration startup on both Render (managed PostgreSQL) and local dev (SQLite):
- If tables already exist (e.g. created previously via create_all) but alembic_version does not,
  it stamps the schema with the base revision (or current state) so alembic knows where to start.
- Runs `alembic upgrade head` safely.
- Works identically on a completely fresh/empty database and on an existing populated database.
"""
import os
import sys
import logging
from pathlib import Path
from sqlalchemy import create_engine, inspect, text
from alembic.config import Config
from alembic import command

logger = logging.getLogger("migration_runner")
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def run_safe_migrations(db_url: str = None) -> None:
    backend_dir = Path(__file__).resolve().parent
    alembic_ini_path = backend_dir / "alembic.ini"
    alembic_cfg = Config(str(alembic_ini_path))
    alembic_cfg.set_main_option("script_location", str(backend_dir / "migrations"))

    if not db_url:
        try:
            from config import settings
            db_url = getattr(settings, "effective_database_url", settings.DATABASE_URL)
        except Exception:
            db_url = os.environ.get("DATABASE_URL", "sqlite:///./dataghost.db")

    # Override sqlalchemy.url in config
    alembic_cfg.set_main_option("sqlalchemy.url", db_url.replace("%", "%%"))

    engine = create_engine(db_url)
    with engine.connect() as conn:
        insp = inspect(conn)
        table_names = set(insp.get_table_names())
        has_alembic_version = "alembic_version" in table_names
        has_existing_tables = ("devices" in table_names) or ("incidents" in table_names)

        if has_existing_tables and not has_alembic_version:
            logger.info("Existing schema detected without alembic_version table. Inspecting columns to stamp revision...")
            # Detect which revision corresponds to the current schema
            dev_cols = {c["name"] for c in insp.get_columns("devices")} if "devices" in table_names else set()
            sl_cols = {c["name"] for c in insp.get_columns("scan_logs")} if "scan_logs" in table_names else set()
            f_cols = {c["name"] for c in insp.get_columns("findings")} if "findings" in table_names else set()

            if "scan_sessions" in table_names:
                stamp_rev = "d4e5f6a7b8c9"
            elif "device_token_hash" in dev_cols and "scan_requested" in dev_cols:
                stamp_rev = "c3d4e5f6a7b8"
            elif "findings" in table_names or "scan_id" in sl_cols:
                stamp_rev = "b2c3d4e5f6a7"
            elif "user_id" in dev_cols:
                stamp_rev = "a1b2c3d4e5f6"
            else:
                stamp_rev = "9f7215996874"

            logger.info("Stamping database with revision %s...", stamp_rev)
            command.stamp(alembic_cfg, stamp_rev)

    logger.info("Executing alembic upgrade head...")
    command.upgrade(alembic_cfg, "head")
    logger.info("Database migrations successfully applied.")


if __name__ == "__main__":
    url_arg = sys.argv[1] if len(sys.argv) > 1 else None
    run_safe_migrations(url_arg)
