"""
Email agent poller — pure-Python Gmail I/O, no Make/n8n in the data path.

Loop:
    1. List unread inbox messages not yet labeled AI-Processed
    2. Skip messages already recorded in the SQLite episodic log
    3. Fetch earlier thread messages as drafter context, then run
       agents.email.agent.process_email_from_dict — so follow-up
       replies in a conversation also get informed drafts
    4. DRAFTED   -> create a reply draft in the thread + labels
                    AI-DRAFT, Cat-<category>, Lang-<language>
       ESCALATED -> apply the matching ESCALATE-* label
       SKIPPED   -> just mark processed
    5. Always apply AI-Processed and log the full result (classification,
       outcome, tokens, cost) to the episodic store in SQLite

Nothing is ever sent autonomously: drafts sit in Gmail until a human
reviews and sends them. Escalated and skipped messages get labels only.

Run continuously (Render worker):   python agents/email/poller.py
Run a single pass (cron/testing):   python agents/email/poller.py --once

Environment:
    GMAIL_CLIENT_ID / GMAIL_CLIENT_SECRET / GMAIL_REFRESH_TOKEN  (required)
    OPENROUTER_API_KEY                                           (required)
    HSO_POLL_INTERVAL_SEC   seconds between passes (default 300)
    HSO_GMAIL_QUERY         override the Gmail search query
    HSO_MAX_PER_CYCLE       max messages per pass (default 10)
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _THIS_DIR.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from shared.gmail_client import GmailClient, GmailError  # noqa: E402
from shared import episodic_store  # noqa: E402
from shared import kb_sync  # noqa: E402

logger = logging.getLogger("poller")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

POLL_INTERVAL_SEC = int(os.environ.get("HSO_POLL_INTERVAL_SEC", "300"))
MAX_PER_CYCLE = int(os.environ.get("HSO_MAX_PER_CYCLE", "10"))
GMAIL_QUERY = os.environ.get(
    "HSO_GMAIL_QUERY",
    "in:inbox is:unread -label:AI-Processed",
)

PROCESSED_LABEL = "AI-Processed"
DRAFT_LABEL = "AI-DRAFT"

CATEGORY_LABELS = [
    "Cat-services_enquiry", "Cat-volunteer_enquiry", "Cat-donation_enquiry",
    "Cat-gift_shop_enquiry", "Cat-partnership_enquiry", "Cat-general",
]
LANGUAGE_LABELS = [
    "Lang-norwegian", "Lang-english", "Lang-arabic", "Lang-ukrainian",
]
ESCALATION_LABELS = [
    "ESCALATE-urgent_welfare", "ESCALATE-media_press",
    "ESCALATE-funder_communication", "ESCALATE-complaint_or_concern",
    "ESCALATE-large_donation", "ESCALATE-language_not_supported",
    "ESCALATE-unclassified",
]
ALL_LABELS = (
    [PROCESSED_LABEL, DRAFT_LABEL]
    + CATEGORY_LABELS + LANGUAGE_LABELS + ESCALATION_LABELS
)


def map_escalation_label(reason: str) -> str:
    """Map an agent escalation_reason string to a Gmail label."""
    r = (reason or "").lower()
    if "urgent_welfare" in r:
        return "ESCALATE-urgent_welfare"
    if "media_press" in r:
        return "ESCALATE-media_press"
    if "funder_communication" in r:
        return "ESCALATE-funder_communication"
    if "complaint_or_concern" in r:
        return "ESCALATE-complaint_or_concern"
    if r.startswith("large_donation"):
        return "ESCALATE-large_donation"
    if "language_not_supported" in r:
        return "ESCALATE-language_not_supported"
    return "ESCALATE-unclassified"


def get_default_agent_fn():
    """Import lazily so tests can inject a fake agent without pulling in
    model/KB dependencies at module import time."""
    from agents.email import agent
    return agent.process_email_from_dict


# ---------------------------------------------------------------------------
# One polling pass
# ---------------------------------------------------------------------------

def run_once(client: GmailClient, agent_fn=None, labels: dict = None) -> dict:
    """Process one batch of new messages. Returns simple counters."""
    if agent_fn is None:
        agent_fn = get_default_agent_fn()
    if labels is None:
        labels = client.ensure_labels(ALL_LABELS)

    stats = {"seen": 0, "drafted": 0, "escalated": 0, "skipped": 0, "errors": 0}

    message_ids = client.list_message_ids(GMAIL_QUERY, max_results=MAX_PER_CYCLE)
    for mid in message_ids:
        stats["seen"] += 1
        try:
            if episodic_store.is_message_processed(mid):
                client.add_labels(mid, [labels[PROCESSED_LABEL]])
                logger.info("msg=%s already in episodic log; labeled only", mid)
                continue

            payload = client.parse_message(client.get_message(mid))
            thread_id = payload["thread_id"]

            # Earlier messages in the thread give the drafter conversation
            # context, so follow-up replies also get a useful draft.
            payload["thread_history"] = client.get_thread_history(
                thread_id, exclude_message_id=mid,
            )

            result = agent_fn(payload)
            outcome = result["outcome"]
            to_apply = [labels[PROCESSED_LABEL]]
            draft_id = ""

            if outcome == "drafted":
                draft_id = client.create_reply_draft(
                    thread_id=thread_id,
                    to_email=payload["sender_email"],
                    subject=payload["subject"],
                    body=result["draft_body"],
                    in_reply_to=payload.get("rfc822_message_id", ""),
                    references=payload.get("references", ""),
                )
                to_apply.append(labels[DRAFT_LABEL])
                c = result.get("classification") or {}
                cat_label = f"Cat-{c.get('category', '')}"
                lang_label = f"Lang-{c.get('language', '')}"
                if cat_label in labels:
                    to_apply.append(labels[cat_label])
                if lang_label in labels:
                    to_apply.append(labels[lang_label])
                stats["drafted"] += 1
                logger.info("msg=%s outcome=drafted draft=%s cat=%s lang=%s "
                            "tokens=%s cost=$%.4f",
                            mid, draft_id, c.get("category"), c.get("language"),
                            result.get("total_tokens"),
                            result.get("estimated_cost_usd", 0.0))

            elif outcome == "escalated":
                esc = map_escalation_label(result.get("escalation_reason", ""))
                to_apply.append(labels[esc])
                stats["escalated"] += 1
                logger.info("msg=%s outcome=escalated reason=%s label=%s",
                            mid, result.get("escalation_reason"), esc)

            elif outcome == "skipped":
                stats["skipped"] += 1
                logger.info("msg=%s outcome=skipped reason=%s",
                            mid, result.get("skip_reason"))

            else:  # error
                stats["errors"] += 1
                logger.error("msg=%s outcome=error message=%s",
                             mid, result.get("error_message"))
                # Do NOT label or record: leave it for retry next cycle.
                continue

            client.add_labels(mid, to_apply)
            episodic_store.log_result(payload, result, draft_id)

        except GmailError as e:
            stats["errors"] += 1
            logger.error("Gmail error on msg=%s: %s", mid, e)
        except Exception:
            stats["errors"] += 1
            logger.exception("Unexpected error on msg=%s", mid)

    return stats


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="HSO email agent poller")
    parser.add_argument("--once", action="store_true",
                        help="run a single pass and exit")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    client = GmailClient.from_env()
    labels = client.ensure_labels(ALL_LABELS)
    logger.info("Poller started. query=%r interval=%ss max_per_cycle=%s",
                GMAIL_QUERY, POLL_INTERVAL_SEC, MAX_PER_CYCLE)

    while True:
        try:
            # Refresh the sheet-synced live KB first (no-op unless
            # HSO_KB_SHEET_ID is set and the sync interval has elapsed).
            kb_sync.sync_if_due(client.access_token)
            stats = run_once(client, labels=labels)
            if stats["seen"]:
                logger.info("Cycle done: %s", stats)
        except Exception:
            logger.exception("Polling cycle failed; will retry next interval")
        if args.once:
            break
        time.sleep(POLL_INTERVAL_SEC)


if __name__ == "__main__":
    main()
