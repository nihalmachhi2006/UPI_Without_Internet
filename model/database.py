"""
model/database.py

SQLite in-memory database using Python's built-in sqlite3.
Equivalent to the H2 in-memory DB used in the Python version.
In production: swap connection string for PostgreSQL.

Tables
------
accounts     — user balances with optimistic-locking version counter
transactions — settled transaction ledger; unique index on packet_hash
"""

import sqlite3
import threading
from contextlib import contextmanager

# Thread-local storage so every thread gets its own connection (SQLite constraint)
_local = threading.local()
_DB_PATH = ":memory:"  # shared in-memory DB via check_same_thread=False + single conn
_conn: sqlite3.Connection = None
_lock = threading.Lock()


def _get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        raise RuntimeError("Database not initialised — call init_db() first")
    return _conn


@contextmanager
def get_db():
    """Context manager that yields a cursor and commits (or rolls back on error)."""
    conn = _get_conn()
    with _lock:
        cur = conn.cursor()
        try:
            yield cur
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()


def init_db():
    """Create tables. Called once at startup."""
    global _conn
    _conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
    _conn.row_factory = sqlite3.Row

    with get_db() as cur:
        cur.executescript("""
            CREATE TABLE IF NOT EXISTS accounts (
                id          TEXT PRIMARY KEY,
                name        TEXT NOT NULL,
                balance     REAL NOT NULL DEFAULT 0,
                version     INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS transactions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                packet_hash TEXT NOT NULL UNIQUE,
                sender_id   TEXT NOT NULL,
                receiver_id TEXT NOT NULL,
                amount      REAL NOT NULL,
                settled_at  INTEGER NOT NULL
            );
        """)


def seed_accounts():
    """Seed demo accounts — mirrors DemoService.Python."""
    accounts = [
        ("alice",   "Alice",   1000.0),
        ("bob",     "Bob",     500.0),
        ("charlie", "Charlie", 750.0),
        ("diana",   "Diana",   200.0),
        ("eve",     "Eve",     300.0),
    ]
    with get_db() as cur:
        cur.executemany(
            "INSERT OR IGNORE INTO accounts (id, name, balance, version) VALUES (?,?,?,0)",
            accounts,
        )
