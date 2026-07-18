"""
Persistent thread tracking using SQLite.
Prevents duplicate processing across container restarts.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

DB_PATH = Path(os.environ.get("HSO_DB_PATH", "./data/hso.db"))


def _ensure_db():
    """Create DB and table if they don't exist."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS processed_threads (
            thread_id TEXT PRIMARY KEY,
            first_email_id TEXT,
            processed_at TEXT,
            outcome TEXT
        )
    """)
    conn.commit()
    conn.close()


def is_thread_processed(thread_id: str) -> bool:
    """Check if a thread has already been processed."""
    _ensure_db()
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.execute(
        "SELECT 1 FROM processed_threads WHERE thread_id = ?", (thread_id,)
    )
    result = cursor.fetchone() is not None
    conn.close()
    return result


def mark_thread_processed(thread_id: str, email_id: str, outcome: str) -> None:
    """Mark a thread as processed."""
    _ensure_db()
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute(
        """INSERT OR REPLACE INTO processed_threads 
           (thread_id, first_email_id, processed_at, outcome)
           VALUES (?, ?, ?, ?)""",
        (thread_id, email_id, datetime.now(timezone.utc).isoformat(), outcome),
    )
    conn.commit()
    conn.close()
