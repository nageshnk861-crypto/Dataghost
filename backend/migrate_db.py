"""
DataGhost DB migration script.

Idempotent — safe to run multiple times.
Run from the backend/ directory:

    python migrate_db.py

Actions:
1. Bring scan_logs up to the current ORM schema (add missing columns).
2. Add is_simulated to scan_logs and incidents.
3. Create the findings table if it does not exist.
4. Delete (or flag) rows that were inserted by simulation/demo code.
"""

import sqlite3
import os
import sys

DB_PATH = os.path.join(os.path.dirname(__file__), "dataghost.db")

SIMULATED_FILENAMES = (
    "customer_pii_identity_records.csv",
    "ai_chatgpt_prompt_exfiltration.txt",
    "claude_anthropic_model_keys.env",
    "clean_system_architecture.md",
    "clean_project_config.json",
    "high_risk.txt",
    "medium_risk.txt",
    "low_risk.txt",
)

GHOST_DEVICE_PATTERNS = (
    "WINDOWS-WORKSTATION-%",
    "Endpoint-%",
    "HOST-%",
    "MAC-WORKSTATION-%",
    "LINUX-WORKSTATION-%",
)


def column_exists(cur: sqlite3.Cursor, table: str, column: str) -> bool:
    cur.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cur.fetchall())


def table_exists(cur: sqlite3.Cursor, table: str) -> bool:
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
    return cur.fetchone() is not None


def add_column(cur: sqlite3.Cursor, table: str, column: str, definition: str) -> None:
    if not column_exists(cur, table, column):
        print(f"  ADD COLUMN {table}.{column}")
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
    else:
        print(f"  SKIP {table}.{column} (already exists)")


def run_migration() -> None:
    if not os.path.exists(DB_PATH):
        print(f"[ERROR] Database not found at {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    cur = conn.cursor()

    # ── 1. scan_logs ──────────────────────────────────────────────────────────
    print("\n[1] Migrating scan_logs …")
    add_column(cur, "scan_logs", "scan_id",        "TEXT")
    add_column(cur, "scan_logs", "user_id",        "INTEGER")
    add_column(cur, "scan_logs", "organization_id","TEXT DEFAULT 'default-org'")
    add_column(cur, "scan_logs", "status",         "TEXT DEFAULT 'COMPLETED'")
    add_column(cur, "scan_logs", "file_size",      "INTEGER")
    add_column(cur, "scan_logs", "is_simulated",   "INTEGER NOT NULL DEFAULT 0")

    # ── 2. incidents ──────────────────────────────────────────────────────────
    print("\n[2] Migrating incidents …")
    add_column(cur, "incidents", "is_simulated", "INTEGER NOT NULL DEFAULT 0")

    # ── 3. findings table ─────────────────────────────────────────────────────
    print("\n[3] Creating findings table …")
    if not table_exists(cur, "findings"):
        print("  CREATE TABLE findings")
        cur.execute("""
            CREATE TABLE findings (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_log_id      INTEGER REFERENCES scan_logs(id),
                scan_id          TEXT,
                user_id          INTEGER REFERENCES users(id),
                organization_id  TEXT DEFAULT 'default-org',
                device_id        TEXT,
                file_name        TEXT,
                file_hash        TEXT,
                detector_id      TEXT,
                rule_id          TEXT,
                category         TEXT,
                severity         TEXT NOT NULL DEFAULT 'LOW',
                confidence       REAL DEFAULT 1.0,
                risk_score       INTEGER DEFAULT 0,
                line_number      INTEGER DEFAULT 0,
                column_number    INTEGER DEFAULT 0,
                char_start       INTEGER DEFAULT 0,
                char_end         INTEGER DEFAULT 0,
                evidence_redacted TEXT,
                description      TEXT,
                remediation      TEXT,
                fingerprint      TEXT,
                status           TEXT NOT NULL DEFAULT 'OPEN',
                is_simulated     INTEGER NOT NULL DEFAULT 0,
                first_seen_at    DATETIME,
                last_seen_at     DATETIME,
                occurrence_count INTEGER DEFAULT 1,
                created_at       DATETIME,
                updated_at       DATETIME
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS ix_findings_scan_log_id ON findings(scan_log_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_findings_device_id   ON findings(device_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_findings_fingerprint  ON findings(fingerprint)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_findings_severity     ON findings(severity)")
    else:
        # Add is_simulated if the table already exists but lacks the column
        add_column(cur, "findings", "is_simulated", "INTEGER NOT NULL DEFAULT 0")
        print("  findings table already exists — ensured is_simulated column")

    # ── 4. Delete / flag fake data ────────────────────────────────────────────
    print("\n[4] Removing simulated rows …")

    # Mark simulated incidents
    placeholders = ",".join("?" * len(SIMULATED_FILENAMES))
    cur.execute(
        f"UPDATE incidents SET is_simulated=1 WHERE filename IN ({placeholders})",
        SIMULATED_FILENAMES,
    )
    updated_inc = cur.rowcount
    print(f"  Marked {updated_inc} incidents as is_simulated=1")

    # Mark simulated scan_logs
    cur.execute(
        f"UPDATE scan_logs SET is_simulated=1 WHERE filename IN ({placeholders})",
        SIMULATED_FILENAMES,
    )
    updated_sl = cur.rowcount
    print(f"  Marked {updated_sl} scan_logs as is_simulated=1")

    # Mark findings that belong to simulated scan_logs
    cur.execute(
        "UPDATE findings SET is_simulated=1 WHERE scan_log_id IN "
        f"(SELECT id FROM scan_logs WHERE filename IN ({placeholders}))",
        SIMULATED_FILENAMES,
    )
    updated_f = cur.rowcount
    print(f"  Marked {updated_f} findings as is_simulated=1")

    # Delete ghost devices (auto-created with generated names)
    deleted_devs = 0
    for pattern in GHOST_DEVICE_PATTERNS:
        cur.execute("DELETE FROM devices WHERE device_name LIKE ?", (pattern,))
        deleted_devs += cur.rowcount
    print(f"  Deleted {deleted_devs} ghost device rows")

    conn.commit()
    conn.close()
    print("\n[OK] Migration complete.\n")


if __name__ == "__main__":
    run_migration()
