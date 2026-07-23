"""
Episodic memory — SQLite log of every message the agent has handled.

Two jobs:
    1. Per-message dedup (replaces the old per-thread gate in thread_store,
       so follow-up replies in a thread also get drafts)
    2. Activity log: one row per processed message with classification,
       outcome, tokens, and cost. This is the queryable record HSO reviews
       ("what did the agent do this week and what did it cost?").

Lives on the Render persistent disk via HSO_DB_PATH (default ./data/hso.db,
/data/hso.db in production). Shares the DB file with thread_store.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def _db_path() -> Path:
    return Path(os.environ.get("HSO_DB_PATH", "./data/hso.db"))


def _connect() -> sqlite3.Connection:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS email_log (
            message_id   TEXT PRIMARY KEY,
            thread_id    TEXT,
            processed_at TEXT,
            sender       TEXT,
            subject      TEXT,
            language     TEXT,
            category     TEXT,
            confidence   TEXT,
            outcome      TEXT,
            draft_id     TEXT,
            reason       TEXT,
            tokens       INTEGER,
            cost_usd     REAL,
            latency_ms   INTEGER
        )
    """)
    conn.commit()
    return conn


def is_message_processed(message_id: str) -> bool:
    conn = _connect()
    try:
        cur = conn.execute(
            "SELECT 1 FROM email_log WHERE message_id = ?", (message_id,)
        )
        return cur.fetchone() is not None
    finally:
        conn.close()


def log_result(payload: dict, result: dict, draft_id: str = "") -> None:
    c = result.get("classification") or {}
    reason = (
        result.get("escalation_reason")
        or result.get("skip_reason")
        or result.get("error_message")
        or ""
    )
    conn = _connect()
    try:
        conn.execute(
            """INSERT OR REPLACE INTO email_log
               (message_id, thread_id, processed_at, sender, subject,
                language, category, confidence, outcome, draft_id, reason,
                tokens, cost_usd, latency_ms)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                payload.get("message_id", ""),
                payload.get("thread_id", ""),
                datetime.now(timezone.utc).isoformat(),
                payload.get("sender_email", ""),
                payload.get("subject", "")[:200],
                c.get("language", ""),
                c.get("category", ""),
                c.get("confidence", ""),
                result.get("outcome", ""),
                draft_id,
                str(reason)[:300],
                int(result.get("total_tokens") or 0),
                float(result.get("estimated_cost_usd") or 0.0),
                int(result.get("latency_ms") or 0),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def recent(limit: int = 50) -> list[tuple]:
    """Most recent log rows — handy for a quick `sqlite3` check on the disk."""
    conn = _connect()
    try:
        cur = conn.execute(
            "SELECT processed_at, sender, subject, category, outcome, "
            "draft_id, cost_usd FROM email_log "
            "ORDER BY processed_at DESC LIMIT ?", (limit,)
        )
        return cur.fetchall()
    finally:
        conn.close()
