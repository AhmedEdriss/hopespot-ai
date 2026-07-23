"""
Google Sheets -> KB sync.

HSO staff maintain a Google Sheet (in HSO's Drive) with one tab per topic
that changes often: classes, timings, events, volunteer roles. This module
pulls every tab and renders it into markdown files under kb/01_Live/, each
marked status: approved. The drafter loads these alongside the curated KB,
so drafts always quote current schedules — staff never touch GitHub.

Requirements:
    - The refresh token must include the spreadsheets.readonly scope
      (scripts/mint_gmail_token.py requests it)
    - HSO_KB_SHEET_ID env var = the spreadsheet ID (from its URL)
    - The sheet must be accessible to the HSO Google account

Sheet conventions (keep it simple for staff):
    - Tab name becomes the document title ("Classes", "Events", ...)
    - Row 1 = column headers; each following row = one entry
    - Empty rows are skipped; a tab named starting with "_" is ignored
      (scratch space for staff)

Failure-safe: any error leaves the existing KB files untouched and the
agent keeps drafting from the last good sync.
"""

from __future__ import annotations

import logging
import os
import re
import time
import urllib.parse
from datetime import datetime, timezone

import requests

from shared.kb_loader import get_kb_root, clear_cache

logger = logging.getLogger(__name__)

SHEETS_API = "https://sheets.googleapis.com/v4/spreadsheets"
LIVE_SUBDIR = "01_Live"

_last_sync_ts: float = 0.0


def _slug(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug or "sheet"


def fetch_tabs(access_token: str, sheet_id: str) -> dict[str, list[list[str]]]:
    """Return {tab_title: rows} for every non-underscore tab."""
    headers = {"Authorization": f"Bearer {access_token}"}
    meta = requests.get(
        f"{SHEETS_API}/{sheet_id}",
        params={"fields": "sheets.properties.title"},
        headers=headers, timeout=30,
    )
    meta.raise_for_status()
    titles = [
        s["properties"]["title"]
        for s in meta.json().get("sheets", [])
        if not s["properties"]["title"].startswith("_")
    ]
    tabs: dict[str, list[list[str]]] = {}
    for title in titles:
        r = requests.get(
            f"{SHEETS_API}/{sheet_id}/values/{urllib.parse.quote(title)}",
            params={"majorDimension": "ROWS"},
            headers=headers, timeout=30,
        )
        r.raise_for_status()
        tabs[title] = r.json().get("values", [])
    return tabs


def render_markdown(title: str, rows: list[list[str]]) -> str:
    """Render one sheet tab as an approved KB markdown document."""
    today = datetime.now(timezone.utc).date().isoformat()
    fm = (
        "---\n"
        f"title: {title} (live)\n"
        "status: approved\n"
        "source: google-sheet\n"
        f"last_updated: {today}\n"
        "---\n\n"
        f"# {title}\n\n"
        "This information is maintained by HSO staff in a Google Sheet and "
        "synced automatically. It reflects the CURRENT schedule/details — "
        "prefer it over any conflicting information elsewhere in the KB.\n\n"
    )
    rows = [r for r in rows if any(str(c).strip() for c in r)]
    if len(rows) < 2:
        return fm + "(no entries at the moment)\n"

    headers = [str(h).strip() for h in rows[0]]
    width = len(headers)
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * width) + " |",
    ]
    for row in rows[1:]:
        cells = [str(c).strip().replace("|", "/") for c in row][:width]
        cells += [""] * (width - len(cells))
        lines.append("| " + " | ".join(cells) + " |")
    return fm + "\n".join(lines) + "\n"


def sync(access_token: str, sheet_id: str = "", fetch_fn=None) -> bool:
    """Fetch the sheet and (re)write kb/01_Live/*.md.
    Returns True if any file changed. Never raises on fetch errors."""
    sheet_id = sheet_id or os.environ.get("HSO_KB_SHEET_ID", "")
    if not sheet_id:
        return False
    try:
        tabs = (fetch_fn or fetch_tabs)(access_token, sheet_id)
    except Exception as e:
        logger.error("KB sheet sync failed (keeping existing KB): %s", e)
        return False

    live_dir = get_kb_root() / LIVE_SUBDIR
    live_dir.mkdir(parents=True, exist_ok=True)
    changed = False
    wanted_files = set()

    for title, rows in tabs.items():
        path = live_dir / f"{_slug(title)}.md"
        wanted_files.add(path.name)
        content = render_markdown(title, rows)
        # Ignore the volatile last_updated line when comparing.
        strip_date = lambda s: re.sub(r"last_updated: .*", "", s)  # noqa: E731
        if not path.exists() or strip_date(path.read_text(encoding="utf-8")) != strip_date(content):
            path.write_text(content, encoding="utf-8")
            changed = True
            logger.info("KB sync updated %s/%s", LIVE_SUBDIR, path.name)

    # Remove live files whose tab was deleted, so stale info can't linger.
    for path in live_dir.glob("*.md"):
        if path.name not in wanted_files:
            path.unlink()
            changed = True
            logger.info("KB sync removed stale %s/%s", LIVE_SUBDIR, path.name)

    if changed:
        clear_cache()
    return changed


# ---------------------------------------------------------------------------
# Control panel — the same sheet doubles as HSO's interface to the agent.
#   _Activity tab: one row per processed email (agent appends)
#   _Controls tab: "paused" switch staff can flip (agent reads each cycle)
# Underscore-prefixed tabs are already excluded from the KB sync above.
# Requires the read-write spreadsheets scope on the refresh token.
# ---------------------------------------------------------------------------

ACTIVITY_TAB = "_Activity"
CONTROLS_TAB = "_Controls"
ACTIVITY_HEADERS = [
    "time_utc", "sender", "subject", "language", "category",
    "confidence", "outcome", "reason", "draft_id", "tokens", "cost_usd",
]


def _sheet_id() -> str:
    return os.environ.get("HSO_KB_SHEET_ID", "")


def ensure_panel_tabs(access_token: str) -> bool:
    """Create _Activity (with header row) and _Controls tabs if missing."""
    sheet_id = _sheet_id()
    if not sheet_id:
        return False
    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        meta = requests.get(
            f"{SHEETS_API}/{sheet_id}",
            params={"fields": "sheets.properties.title"},
            headers=headers, timeout=30,
        )
        meta.raise_for_status()
        titles = [s["properties"]["title"] for s in meta.json().get("sheets", [])]

        to_add = [t for t in (ACTIVITY_TAB, CONTROLS_TAB) if t not in titles]
        if to_add:
            r = requests.post(
                f"{SHEETS_API}/{sheet_id}:batchUpdate",
                json={"requests": [
                    {"addSheet": {"properties": {"title": t}}} for t in to_add
                ]},
                headers=headers, timeout=30,
            )
            r.raise_for_status()
        if ACTIVITY_TAB in to_add:
            _append_values(access_token, sheet_id, ACTIVITY_TAB,
                           [ACTIVITY_HEADERS])
        if CONTROLS_TAB in to_add:
            _append_values(access_token, sheet_id, CONTROLS_TAB,
                           [["setting", "value", "notes"],
                            ["paused", "no",
                             "set to yes to stop the agent processing email"]])
        return True
    except Exception as e:
        logger.error("ensure_panel_tabs failed: %s", e)
        return False


def _append_values(access_token: str, sheet_id: str, tab: str,
                   values: list[list]) -> None:
    r = requests.post(
        f"{SHEETS_API}/{sheet_id}/values/"
        f"{urllib.parse.quote(tab + '!A1')}:append",
        params={"valueInputOption": "RAW", "insertDataOption": "INSERT_ROWS"},
        json={"values": values},
        headers={"Authorization": f"Bearer {access_token}"}, timeout=30,
    )
    r.raise_for_status()


def append_activity(access_token: str, payload: dict, result: dict,
                    draft_id: str = "") -> bool:
    """Append one processed-email row to the _Activity tab. Best-effort:
    a failure here must never break email processing."""
    sheet_id = _sheet_id()
    if not sheet_id:
        return False
    try:
        c = result.get("classification") or {}
        reason = (result.get("escalation_reason")
                  or result.get("skip_reason")
                  or result.get("error_message") or "")
        row = [
            datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            payload.get("sender_email", ""),
            payload.get("subject", "")[:100],
            c.get("language", ""), c.get("category", ""),
            c.get("confidence", ""), result.get("outcome", ""),
            str(reason)[:200], draft_id,
            int(result.get("total_tokens") or 0),
            round(float(result.get("estimated_cost_usd") or 0.0), 5),
        ]
        _append_values(access_token, sheet_id, ACTIVITY_TAB, [row])
        return True
    except Exception as e:
        logger.error("append_activity failed (continuing): %s", e)
        return False


def is_paused(access_token: str) -> bool:
    """Read the paused switch from _Controls. Fails open: if the sheet is
    unreachable, the agent keeps working."""
    sheet_id = _sheet_id()
    if not sheet_id:
        return False
    try:
        r = requests.get(
            f"{SHEETS_API}/{sheet_id}/values/"
            f"{urllib.parse.quote(CONTROLS_TAB + '!A1:B20')}",
            headers={"Authorization": f"Bearer {access_token}"}, timeout=30,
        )
        r.raise_for_status()
        for row in r.json().get("values", []):
            if row and str(row[0]).strip().lower() == "paused":
                value = str(row[1]).strip().lower() if len(row) > 1 else "no"
                return value in ("yes", "true", "1", "on")
        return False
    except Exception as e:
        logger.error("is_paused check failed (assuming not paused): %s", e)
        return False


def sync_if_due(access_token_fn, interval_sec: int = None) -> bool:
    """Call from the poller loop; runs a sync at most every interval_sec."""
    global _last_sync_ts
    if not os.environ.get("HSO_KB_SHEET_ID"):
        return False
    if interval_sec is None:
        interval_sec = int(os.environ.get("HSO_KB_SYNC_INTERVAL_SEC", "21600"))
    if time.time() - _last_sync_ts < interval_sec:
        return False
    _last_sync_ts = time.time()
    try:
        return sync(access_token_fn())
    except Exception as e:
        logger.error("KB sync failed: %s", e)
        return False
