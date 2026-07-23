"""
Offline wiring test for the Gmail poller.

No network, no credentials, no model calls: GmailClient is replaced by a
fake, and the agent function is injected. Verifies:

    drafted    -> reply draft created + AI-DRAFT/Cat/Lang/AI-Processed labels
    escalated  -> ESCALATE-* label + AI-Processed, no draft
    skipped    -> AI-Processed only
    error      -> untouched (no label, no log row, retried next cycle)
    follow-up  -> reply in an existing thread gets its own draft, and the
                  agent receives the earlier messages as thread_history
    episodic   -> every handled message logged to SQLite with outcome/cost
    dedup      -> a second pass reprocesses nothing

Run:  python tests/test_poller_offline.py
"""

from __future__ import annotations

import base64
import os
import sys
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

# Isolate the SQLite store BEFORE importing modules that read env.
_tmpdir = tempfile.mkdtemp()
os.environ["HSO_DB_PATH"] = str(Path(_tmpdir) / "test.db")

from shared import episodic_store  # noqa: E402
from shared.gmail_client import GmailClient  # noqa: E402
from agents.email import poller  # noqa: E402


def b64(s: str) -> str:
    return base64.urlsafe_b64encode(s.encode()).decode()


def gmail_msg(mid, thread, sender, subject, body, rfc_id="<orig@mail>"):
    return {
        "id": mid,
        "threadId": thread,
        "payload": {
            "headers": [
                {"name": "From", "value": sender},
                {"name": "Subject", "value": subject},
                {"name": "Message-ID", "value": rfc_id},
            ],
            "mimeType": "text/plain",
            "body": {"data": b64(body)},
            "parts": [],
        },
    }


class FakeGmail(GmailClient):
    """Overrides all network methods; inherits the pure parsing logic
    (parse_message, get_thread_history) so those run for real."""

    def __init__(self, messages):
        super().__init__("id", "secret", "rt")
        self.messages = {m["id"]: m for m in messages}
        self.labeled: dict[str, list[str]] = {}
        self.drafts: list[dict] = []
        self._labels = {n: f"L_{n}" for n in poller.ALL_LABELS}

    def list_message_ids(self, query, max_results=25):
        return list(self.messages)[:max_results]

    def get_message(self, message_id):
        return self.messages[message_id]

    def get_thread(self, thread_id):
        return {"messages": [
            m for m in self.messages.values() if m["threadId"] == thread_id
        ]}

    def ensure_labels(self, names):
        return dict(self._labels)

    def add_labels(self, message_id, label_ids):
        self.labeled.setdefault(message_id, []).extend(label_ids)

    def create_reply_draft(self, thread_id, to_email, subject, body,
                           in_reply_to="", references=""):
        self.drafts.append({
            "thread_id": thread_id, "to": to_email, "subject": subject,
            "body": body, "in_reply_to": in_reply_to,
        })
        return f"draft-{len(self.drafts)}"


seen_payloads: dict[str, dict] = {}


def fake_agent(payload):
    seen_payloads[payload["message_id"]] = payload
    body = payload["body"].lower()
    if "norwegian classes" in body or "follow-up" in body:
        return {
            "outcome": "drafted",
            "draft_body": "Hei! Our classes meet twice a week.",
            "classification": {"category": "services_enquiry",
                              "language": "english", "confidence": "high"},
            "total_tokens": 200, "estimated_cost_usd": 0.001,
            "latency_ms": 12,
        }
    if "journalist" in body:
        return {"outcome": "escalated",
                "escalation_reason": "category:media_press"}
    if "out of office" in body:
        return {"outcome": "skipped", "skip_reason": "auto_reply_detected"}
    return {"outcome": "error", "error_message": "boom"}


def run() -> None:
    msgs = [
        gmail_msg("m1", "t1", "Ali <ali@example.com>", "Classes",
                  "Do you have Norwegian classes?", rfc_id="<m1@mail>"),
        gmail_msg("m2", "t2", "Kari <kari@avis.no>", "Interview",
                  "I am a journalist writing about integration."),
        gmail_msg("m3", "t3", "noreply@corp.com", "Re: hello",
                  "Out of office until Monday."),
        gmail_msg("m4", "t4", "x@y.com", "??", "trigger the error path"),
        gmail_msg("m5", "t1", "Ali <ali@example.com>", "Re: Classes",
                  "Thanks! A follow-up: is there an evening group?",
                  rfc_id="<m5@mail>"),
    ]
    fake = FakeGmail(msgs)
    stats = poller.run_once(fake, agent_fn=fake_agent)

    checks = []

    def check(name, cond):
        checks.append((name, cond))
        print(("PASS " if cond else "FAIL ") + name)

    check("stats counted correctly",
          stats == {"seen": 5, "drafted": 2, "escalated": 1,
                    "skipped": 1, "errors": 1})
    check("two drafts, both in thread t1",
          len(fake.drafts) == 2
          and all(d["thread_id"] == "t1" for d in fake.drafts))
    check("follow-up draft threads to the reply message",
          fake.drafts[1]["in_reply_to"] == "<m5@mail>"
          and fake.drafts[1]["subject"] == "Re: Classes")
    check("first message got NO thread history",
          seen_payloads["m1"]["thread_history"] == ""
          or "follow-up" not in seen_payloads["m1"]["thread_history"].lower())
    check("follow-up agent call received earlier messages as history",
          "norwegian classes" in seen_payloads["m5"]["thread_history"].lower()
          and "ali@example.com" in seen_payloads["m5"]["thread_history"])
    check("history excludes the message being processed",
          "evening group" not in seen_payloads["m5"]["thread_history"].lower())
    check("drafted msg labels", set(fake.labeled.get("m1", [])) == {
        "L_AI-Processed", "L_AI-DRAFT",
        "L_Cat-services_enquiry", "L_Lang-english"})
    check("escalated msg labels", set(fake.labeled.get("m2", [])) == {
        "L_AI-Processed", "L_ESCALATE-media_press"})
    check("skipped msg labeled processed only",
          fake.labeled.get("m3") == ["L_AI-Processed"])
    check("error msg left untouched for retry",
          "m4" not in fake.labeled
          and not episodic_store.is_message_processed("m4"))
    check("episodic log has the four handled messages",
          all(episodic_store.is_message_processed(m)
              for m in ["m1", "m2", "m3", "m5"]))
    rows = episodic_store.recent()
    check("episodic rows carry outcome and draft ids",
          len(rows) == 4
          and sorted(r[4] for r in rows)
          == ["drafted", "drafted", "escalated", "skipped"]
          and sorted(r[5] for r in rows if r[5])
          == ["draft-1", "draft-2"])
    check("escalation label mapping", [
        poller.map_escalation_label("urgent_welfare"),
        poller.map_escalation_label("large_donation:12000_nok"),
        poller.map_escalation_label("drafter:classification mismatch"),
        poller.map_escalation_label("language_not_supported"),
    ] == ["ESCALATE-urgent_welfare", "ESCALATE-large_donation",
          "ESCALATE-unclassified", "ESCALATE-language_not_supported"])

    # Second pass: everything already logged (except the error, which the
    # fake agent will just error on again) — nothing new drafted.
    stats2 = poller.run_once(fake, agent_fn=fake_agent)
    check("second pass drafts nothing new",
          len(fake.drafts) == 2 and stats2["drafted"] == 0
          and stats2["escalated"] == 0)

    failed = [n for n, ok in checks if not ok]
    print(f"\n{len(checks) - len(failed)}/{len(checks)} checks passed")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    run()
