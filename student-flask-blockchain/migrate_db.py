"""Safe SQLite schema migration helper.

Currently ensures `blockchain_tx_log.action` column exists.

Constraints:
- Do NOT reset database
- Do NOT delete data
- Only ALTER TABLE when a column is missing
"""

from __future__ import annotations

import os
import sqlite3
import logging
from typing import Optional


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.path.join(BASE_DIR, "database")
DEFAULT_DB_PATH = os.path.join(DB_DIR, "student.db")


logger = logging.getLogger("migrate_db")
if not logger.handlers:
    # Minimal console logger (safe for local dev)
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def _get_connection(db_path: str) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    # ensure we can query schema info consistently
    conn.row_factory = sqlite3.Row
    return conn


def _table_has_column(conn: sqlite3.Connection, table_name: str, column_name: str) -> bool:
    cur = conn.execute(f"PRAGMA table_info({table_name});")
    rows = cur.fetchall()
    for r in rows:
        # PRAGMA table_info columns: cid, name, type, notnull, dflt_value, pk
        if r["name"] == column_name:
            return True
    return False


def ensure_blockchain_tx_log_schema(db_path: str = DEFAULT_DB_PATH) -> None:
    """Ensure blockchain_tx_log schema is compatible with current SQLAlchemy model.

    Specifically:
    - add `action` TEXT if missing
    """

    conn: Optional[sqlite3.Connection] = None
    try:
        conn = _get_connection(db_path)

        table_name = "blockchain_tx_log"
        if not _table_has_column(conn, table_name, "id"):
            # Table might not exist yet; in that case we do nothing here and let SQLAlchemy create it.
            # This helper is specifically for schema mismatch of existing tables.
            logger.info("Table %s not found or has no column 'id'; skipping schema ensure.", table_name)
            return

        if _table_has_column(conn, table_name, "action"):
            logger.info("Schema OK: %s.action already exists.", table_name)
            return

        # Safe migration: add column without touching existing rows.
        logger.info("Migrating schema: adding missing column %s.%s ...", table_name, "action")
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN action TEXT;")
        conn.commit()
        logger.info("Migration complete: %s.%s added.", table_name, "action")

    except Exception as e:
        # Raise so caller can decide whether to crash or not.
        raise RuntimeError(f"Failed to ensure schema for blockchain_tx_log.action: {e}") from e
    finally:
        if conn is not None:
            conn.close()


def main() -> int:
    db_path = os.environ.get("DATABASE_PATH", DEFAULT_DB_PATH)
    try:
        ensure_blockchain_tx_log_schema(db_path=db_path)
        return 0
    except Exception as e:
        logger.exception("DB migration failed: %s", e)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

