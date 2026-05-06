"""
Email Agent CLI Runner

Test the agent from the command line without needing Gmail or a real inbox.

Usage:
    # Run on a single email file (JSON)
    python agents/email/run_cli.py --email tests/sample_emails/01_services_norwegian.json

    # Run on all sample emails in a folder
    python agents/email/run_cli.py --folder tests/sample_emails/

    # Quick demo (uses the hardcoded email in agent.py)
    python agents/email/run_cli.py --demo
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _THIS_DIR.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from agents.email import agent  # noqa: E402


def load_email_from_file(path: Path) -> agent.IncomingEmail:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return agent.IncomingEmail(
        message_id=payload.get("message_id", path.stem),
        thread_id=payload.get("thread_id", path.stem),
        sender_email=payload["sender_email"],
        sender_name=payload.get("sender_name", ""),
        subject=payload.get("subject", ""),
        body=payload["body"],
        attachment_count=payload.get("attachment_count", 0),
    )


def print_result(email: agent.IncomingEmail, result: agent.AgentResult) -> None:
    border = "=" * 72
    print(f"\n{border}")
    print(f"EMAIL: {email.message_id}")
    print(f"From:  {email.sender_name} <{email.sender_email}>")
    print(f"Subject: {email.subject}")
    body_preview = email.body[:300] + ("..." if len(email.body) > 300 else "")
    print(f"\nBody:\n{body_preview}")
    print(f"\n{'-' * 72}")
    print(f"OUTCOME: {result.outcome.value}")

    if result.classification:
        c = result.classification
        print(f"Classified: {c.language.value} / {c.category.value} / {c.confidence}")
        print(f"  welfare_signals={c.welfare_signals}")
        print(f"  notes={c.notes}")

    if result.skip_reason:
        print(f"Skip reason: {result.skip_reason}")
    if result.escalation_reason:
        print(f"Escalation reason: {result.escalation_reason}")
    if result.error_message:
        print(f"Error: {result.error_message}")
    if result.draft_body:
        print(f"\n--- DRAFT ---\n{result.draft_body}\n--- END DRAFT ---")

    print(f"\nTokens: {result.total_tokens}")
    print(f"Cost:   ${result.estimated_cost_usd:.4f}")
    print(f"Latency: {result.latency_ms} ms")
    print(border)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run HSO email agent on test emails")
    parser.add_argument("--email", type=Path, help="Single email JSON file")
    parser.add_argument("--folder", type=Path, help="Folder of email JSON files")
    parser.add_argument("--demo", action="store_true", help="Hardcoded demo email")
    args = parser.parse_args()

    emails: list[agent.IncomingEmail] = []

    if args.demo:
        emails.append(agent.IncomingEmail(
            message_id="demo-001",
            thread_id="demo-thread-001",
            sender_email="newcomer@example.com",
            sender_name="Ali",
            subject="Norwegian classes",
            body=(
                "Hi, I just moved to Trondheim from Iraq last month. My "
                "English is okay but my Norwegian is very basic. Do you "
                "have classes I could join?"
            ),
        ))

    if args.email:
        if not args.email.exists():
            print(f"File not found: {args.email}", file=sys.stderr)
            return 1
        emails.append(load_email_from_file(args.email))

    if args.folder:
        if not args.folder.is_dir():
            print(f"Not a folder: {args.folder}", file=sys.stderr)
            return 1
        for p in sorted(args.folder.glob("*.json")):
            emails.append(load_email_from_file(p))

    if not emails:
        parser.print_help()
        return 1

    total_cost = 0.0
    outcomes: dict[str, int] = {}

    for email in emails:
        result = agent.process_email(email)
        print_result(email, result)
        total_cost += result.estimated_cost_usd
        outcomes[result.outcome.value] = outcomes.get(result.outcome.value, 0) + 1

    print(f"\n{'#' * 72}")
    print(f"SUMMARY: {len(emails)} email(s) processed")
    for outcome, count in sorted(outcomes.items()):
        print(f"  {outcome}: {count}")
    print(f"  Total cost: ${total_cost:.4f}")
    print('#' * 72)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
