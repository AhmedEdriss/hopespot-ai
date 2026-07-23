"""
Offline test for the Google Sheets -> KB sync.

No network: the fetch function is injected. Verifies rendering, approved
status, change detection, stale-file removal, failure-safety, and that
the synced content reaches the drafter via kb_loader.load_live_context().

Run:  python tests/test_kb_sync_offline.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

_tmpdir = tempfile.mkdtemp()
os.environ["HSO_KB_PATH"] = _tmpdir
os.environ["HSO_KB_SHEET_ID"] = "test-sheet-id"

from shared import kb_sync, kb_loader  # noqa: E402

TABS_V1 = {
    "Classes": [
        ["Course", "Level", "Day", "Time", "Location"],
        ["Norwegian A1", "Beginner", "Tuesday", "17:00-19:00", "HSO office"],
        ["Norwegian A2", "Elementary", "Thursday", "17:00-19:00", "HSO office"],
        [],  # empty row should be skipped
    ],
    "Events": [
        ["Event", "Date", "Notes"],
        ["Eid celebration", "2026-08-15", "Open | to everyone"],
    ],
}


def run() -> None:
    checks = []

    def check(name, cond):
        checks.append((name, cond))
        print(("PASS " if cond else "FAIL ") + name)

    changed = kb_sync.sync("fake-token", fetch_fn=lambda t, s: TABS_V1)
    live = Path(_tmpdir) / "01_Live"
    classes = (live / "classes.md").read_text()
    events = (live / "events.md").read_text()

    check("first sync reports change and writes both files", changed
          and (live / "classes.md").exists() and (live / "events.md").exists())
    check("rendered as approved KB docs",
          "status: approved" in classes and "source: google-sheet" in classes)
    check("table content rendered",
          "| Norwegian A1 | Beginner | Tuesday | 17:00-19:00 | HSO office |" in classes)
    check("pipe characters in cells sanitized",
          "Open / to everyone" in events)
    check("no change -> no rewrite",
          kb_sync.sync("fake-token", fetch_fn=lambda t, s: TABS_V1) is False)

    ctx = kb_loader.load_live_context()
    check("live context reaches the drafter loader",
          "Norwegian A1" in ctx and "Eid celebration" in ctx
          and "01_Live/classes.md" in ctx)

    # Edit a cell -> change detected; delete a tab -> stale file removed.
    tabs_v2 = {"Classes": [
        ["Course", "Level", "Day", "Time", "Location"],
        ["Norwegian A1", "Beginner", "WEDNESDAY", "18:00-20:00", "HSO office"],
    ]}
    changed2 = kb_sync.sync("fake-token", fetch_fn=lambda t, s: tabs_v2)
    check("edit detected and stale events.md removed",
          changed2 and not (live / "events.md").exists()
          and "WEDNESDAY" in (live / "classes.md").read_text())
    check("cache cleared: drafter sees the update",
          "WEDNESDAY" in kb_loader.load_live_context()
          and "Eid celebration" not in kb_loader.load_live_context())

    def boom(t, s):
        raise RuntimeError("sheets api down")

    check("fetch failure keeps existing KB",
          kb_sync.sync("fake-token", fetch_fn=boom) is False
          and (live / "classes.md").exists())

    empty_tab = {"Classes": [["Course", "Level"]]}
    kb_sync.sync("fake-token", fetch_fn=lambda t, s: empty_tab)
    check("header-only tab renders 'no entries'",
          "no entries at the moment" in (live / "classes.md").read_text())

    failed = [n for n, ok in checks if not ok]
    print(f"\n{len(checks) - len(failed)}/{len(checks)} checks passed")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    run()
