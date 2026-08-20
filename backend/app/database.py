"""
SQLite connection helpers.

Phase 13 adds the real schema — agents, rounds, answers, evaluations,
votes, eliminations, evolutions — so a run survives a restart and
questions like "what happened to the Scientist in Round 5?" can be
answered from disk instead of only from an in-memory ArenaEngine.
The `meta` table from Phase 0 stays too, for small housekeeping values.
"""
import logging
import sqlite3
from contextlib import contextmanager
from typing import Iterator

from app.config import settings

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agents (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    system_prompt TEXT,
    specialties TEXT,      -- JSON array
    weaknesses TEXT,       -- JSON array
    generation INTEGER NOT NULL DEFAULT 0,
    parent_agent TEXT,
    model TEXT
);

CREATE TABLE IF NOT EXISTS rounds (
    round_number INTEGER PRIMARY KEY,
    question TEXT NOT NULL,
    total_time_ms REAL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS answers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    round_number INTEGER NOT NULL,
    agent_id TEXT NOT NULL,
    model TEXT,
    answer TEXT,
    success INTEGER NOT NULL,
    generation_time_ms REAL,
    error TEXT
);

CREATE TABLE IF NOT EXISTS evaluations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    round_number INTEGER NOT NULL,
    judge_name TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    accuracy INTEGER,
    reasoning INTEGER,
    utility INTEGER,
    overall REAL,
    critique TEXT
);

CREATE TABLE IF NOT EXISTS votes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    round_number INTEGER NOT NULL,
    voter_agent_id TEXT NOT NULL,
    voted_for_agent_id TEXT,
    success INTEGER NOT NULL,
    error TEXT
);

CREATE TABLE IF NOT EXISTS eliminations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    round_number INTEGER NOT NULL,
    agent_id TEXT NOT NULL,
    personality_name TEXT,
    final_score REAL,
    reason TEXT
);

CREATE TABLE IF NOT EXISTS evolutions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    round_number INTEGER NOT NULL,
    child_id TEXT NOT NULL,
    parent_id TEXT,
    name TEXT,
    description TEXT,
    system_prompt TEXT,
    specialties TEXT,       -- JSON array
    weaknesses TEXT,        -- JSON array
    generation INTEGER
);
"""


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
    """Create every table if it doesn't already exist. Safe to call on
    every startup — CREATE TABLE IF NOT EXISTS is idempotent, which is
    exactly what "survive a restart" requires."""
    with db_cursor() as cur:
        cur.executescript(_SCHEMA)
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