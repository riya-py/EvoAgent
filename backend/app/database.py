"""
SQLite connection helpers.

Phase 0 just needs the database to exist and be reachable — the real
tables (agents, rounds, answers, evaluations, votes, eliminations,
evolutions) get created in Phase 13 once we know their final shape.
For now we create a tiny `meta` table so init_db() has something
concrete to verify, and so `GET /api/health` can prove the DB works.
"""
import logging
import sqlite3
from contextlib import contextmanager
from typing import Iterator

from app.config import settings

logger = logging.getLogger(__name__)


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.database_full_path)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def db_cursor() -> Iterator[sqlite3.Cursor]:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        yield cursor
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    """Create the placeholder meta table if it doesn't already exist."""
    with db_cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
    logger.info("Database initialized at %s", settings.database_full_path)


def check_db() -> bool:
    """Used by /api/health to confirm SQLite is reachable and writable."""
    try:
        with db_cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        return True
    except sqlite3.Error:
        logger.exception("Database health check failed")
        return False