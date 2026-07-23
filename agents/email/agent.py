"""
HSO Email Agent — Reference Implementation

Reads incoming emails, classifies them, and either drafts a reply (using
HSO's voice and KB) or escalates to a human.

This module focuses purely on the agent logic. The orchestrator
(the Gmail poller, Make.com / n8n, or cron) handles the surface integration:
    - Watching the inbox
    - Creating Gmail drafts
    - Logging activity
    - Notifying reviewers

All model calls go through `shared.model_gateway`, so swapping from Claude
to GPT to Gemini is a config change (set HSO_MODEL_DRAFTER), not a code
change.

All KB reads go through `shared.kb_loader`.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

# Allow running this module from anywhere — find the project root.
_THIS_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _THIS_DIR.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from shared.model_gateway import (  # noqa: E402
    ModelError, call_model, estimate_cost_usd, resolve_model,
)
from shared.kb_loader import (  # noqa: E402
    load_core_context, load_category_context, load_live_context,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Configuration
# ============================================================================

MODEL_CLASSIFIER = "classifier"
MODEL_DRAFTER = "drafter"

DONATION_ESCALATION_THRESHOLD_NOK = int(
    os.environ.get("HSO_DONATION_THRESHOLD_NOK", "5000")
)

INTERNAL_DOMAINS = ["hopespot.no", "hope.spot.org"]

AUTO_REPLY_INDICATORS = [
    "auto-reply", "auto reply", "out of office",
    "delivery failure", "undeliverable", "mail delivery",
    "automatisk svar",
]


# ============================================================================
# Data Types
# ============================================================================

class Category(str, Enum):
    SERVICES = "services_enquiry"
    VOLUNTEER = "volunteer_enquiry"
    DONATION = "donation_enquiry"
    GIFT_SHOP = "gift_shop_enquiry"
    PARTNERSHIP = "partnership_enquiry"
    MEDIA = "media_press"
    FUNDER = "funder_communication"
    COMPLAINT = "complaint_or_concern"
    URGENT_WELFARE = "urgent_welfare"
    GENERAL = "general"


class Language(str, Enum):
    NORWEGIAN = "norwegian"
    ENGLISH = "english"
    ARABIC = "arabic"
    UKRAINIAN = "ukrainian"
    OTHER = "other"


class Outcome(str, Enum):
    DRAFTED = "drafted"
    ESCALATED = "escalated"
    SKIPPED = "skipped"
    ERROR = "error"


ALWAYS_ESCALATE = {
    Category.MEDIA, Category.FUNDER,
    Category.COMPLAINT, Category.URGENT_WELFARE,
}

CATEGORY_TO_KB_FILES: dict[str, list[str]] = {
    Category.SERVICES.value: ["02_FAQs/services.md"],
    Category.VOLUNTEER.value: ["02_FAQs/volunteering.md"],
    Category.DONATION.value: ["02_FAQs/donations.md"],
    Category.GIFT_SHOP.value: ["02_FAQs/gift-shop.md", "05_Gift_Shop/products.md"],
    Category.PARTNERSHIP.value: ["02_FAQs/partnerships.md"],
    Category.GENERAL.value: [
        "02_FAQs/services.md",
        "02_FAQs/volunteering.md",
        "02_FAQs/donations.md",
    ],
}


@dataclass
class IncomingEmail:
    message_id: str
    thread_id: str
    sender_email: str
    sender_name: str
    subject: str
    body: str
    received_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    has_attachments: bool = False
    attachment_count: int = 0
    thread_history: str = ""  # earlier messages in this thread, oldest first


@dataclass
class Classification:
    language: Language
    category: Category
    confidence: str
    welfare_signals: bool
    notes: str
    raw_response: str = ""
    tokens_used: int = 0


@dataclass
class AgentResult:
    outcome: Outcome
    email_message_id: str
    classification: Optional[Classification] = None
    draft_body: Optional[str] = None
    escalation_reason: Optional[str] = None
    skip_reason: Optional[str] = None
    error_message: Optional[str] = None
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    latency_ms: int = 0

    def to_dict(self) -> dict:
        d = asdict(self)
        if self.classification:
            d["classification"]["language"] = self.classification.language.value
            d["classification"]["category"] = self.classification.category.value
        d["outcome"] = self.outcome.value
        return d


# ============================================================================
# Step 1 — Filter
# ============================================================================

def should_skip(email: IncomingEmail) -> Optional[str]:
    sender_domain = email.sender_email.split("@")[-1].lower()
    if any(d in sender_domain for d in INTERNAL_DOMAINS):
        return "internal_sender"

    subject_lower = email.subject.lower()
    body_start = email.body[:500].lower()
    for indicator in AUTO_REPLY_INDICATORS:
        if indicator in subject_lower or indicator in body_start:
            return f"auto_reply_detected:{indicator}"

    if len(email.body.strip()) < 10:
        return "body_too_short"

    if email.attachment_count > 3:
        return "too_many_attachments"

    return None


# ============================================================================
# Step 2 — Classify
# ============================================================================

# This prompt is written for portability across model families. Key choices:
#   - Explicit JSON-only output instruction; no markdown reliance
#   - Many worked examples (few-shot grounds models toward consistent behavior)
#   - No reliance on Claude-specific features
#   - System message used the same way OpenAI/Anthropic both expect
CLASSIFIER_SYSTEM_PROMPT = """You are a classifier for Hope Spot Organization \
(HSO), a Norwegian NGO that helps refugees and immigrants. Your only job is \
to read an incoming email and output structured JSON.

# Output format

Respond ONLY with valid JSON in this exact structure:

{
  "language": "<one of: norwegian, english, arabic, ukrainian, other>",
  "category": "<one of the categories listed below>",
  "confidence": "<high, medium, or low>",
  "welfare_signals": <true or false>,
  "notes": "<brief reason, max 20 words>"
}

No preamble. No explanation. No markdown formatting. Only the JSON object.

# Categories

- services_enquiry: language classes, job training, counseling, schedules
- volunteer_enquiry: wanting to volunteer or asking about volunteer roles
- donation_enquiry: how to donate, donation receipts, recurring gifts
- gift_shop_enquiry: gift shop products, ordering, shipping
- partnership_enquiry: an organization or business wanting to collaborate
- media_press: journalists asking for comment, interview, or information
- funder_communication: from a funder — government agencies, foundations
- complaint_or_concern: dissatisfaction or complaints
- urgent_welfare: safety concerns, mental health crisis, abuse, danger
- general: doesn't clearly fit, or unclear intent

# Welfare signals

Set welfare_signals=true for any mention of: self-harm, suicidal thoughts, \
physical danger, threats, domestic violence, abuse, children in danger, \
being trapped, immediate medical emergency, homelessness/urgent housing, \
trafficking. Err on the side of flagging.

If welfare_signals=true, category should typically be urgent_welfare unless \
the welfare mention is clearly historical or about a third party.

# Confidence

high: clearly fits one category | medium: ambiguous | low: difficult

Use "low" liberally when uncertain.

# Examples

Email: "Hei, jeg lurer på når norskkursene starter? Jeg er ny i Trondheim."
Output: {"language": "norwegian", "category": "services_enquiry", "confidence": "high", "welfare_signals": false, "notes": "Asking when Norwegian classes start"}

Email: "I would like to donate 10000 NOK to your work."
Output: {"language": "english", "category": "donation_enquiry", "confidence": "high", "welfare_signals": false, "notes": "Donation enquiry, 10000 NOK"}

Email: "I cannot continue like this. I have nowhere to go and my husband does not let me work or leave."
Output: {"language": "english", "category": "urgent_welfare", "confidence": "high", "welfare_signals": true, "notes": "Domestic control, isolation"}

Email: "Hi, I'm writing for Aftenposten about refugee integration."
Output: {"language": "english", "category": "media_press", "confidence": "high", "welfare_signals": false, "notes": "Aftenposten interview request"}

Email: "السلام عليكم، أنا من سوريا ووصلت حديثاً. هل تساعدوننا في تعلم اللغة؟"
Output: {"language": "arabic", "category": "services_enquiry", "confidence": "high", "welfare_signals": false, "notes": "From Syria, asking about language help"}

Email: "Application reference 2026-IMDI-0847: Please submit your interim report by 15.06.2026."
Output: {"language": "english", "category": "funder_communication", "confidence": "high", "welfare_signals": false, "notes": "IMDi grant reporting deadline"}
"""


def classify_email(email: IncomingEmail) -> Classification:
    user_message = (
        f"Subject: {email.subject}\n\n"
        f"Body:\n{email.body}\n\n"
        f"---\nClassify this email."
    )

    response = call_model(
        model=MODEL_CLASSIFIER,
        system_prompt=CLASSIFIER_SYSTEM_PROMPT,
        user_message=user_message,
        max_tokens=200,
        temperature=0.0,
    )

    raw = response.content.strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.MULTILINE).strip()

    try:
        data = json.loads(raw)
        return Classification(
            language=Language(data["language"]),
            category=Category(data["category"]),
            confidence=data["confidence"],
            welfare_signals=bool(data["welfare_signals"]),
            notes=data.get("notes", "")[:200],
            raw_response=raw,
            tokens_used=response.tokens_used,
        )
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        logger.warning("Classifier parse error: %s", e)
        return Classification(
            language=Language.OTHER,
            category=Category.GENERAL,
            confidence="low",
            welfare_signals=False,
            notes=f"classifier_parse_error: {str(e)[:100]}",
            raw_response=raw,
            tokens_used=response.tokens_used,
        )


# ============================================================================
# Step 3 — Route
# ============================================================================

def detect_donation_amount(body: str) -> Optional[int]:
    """Returns NOK amount if found. Handles Norwegian and US number formats."""
    text = body.lower()
    text = re.sub(r"(\d),-", r"\1 ", text)  # Strip Norwegian ",-" suffix

    pattern = r"(\d{1,3}(?:[\s,.]\d{3})*(?:[,.]\d{1,2})?)\s*(?:nok|kr|kroner)\b"
    amounts: list[int] = []

    for match in re.finditer(pattern, text):
        num_str = match.group(1)
        if "," in num_str and "." not in num_str:
            parts = num_str.split(",")
            if len(parts[-1]) == 3:
                cleaned = num_str.replace(",", "").replace(" ", "").replace(".", "")
            else:
                cleaned = num_str.replace(" ", "").replace(".", "").replace(",", ".")
        elif "." in num_str and "," in num_str:
            if num_str.rfind(",") > num_str.rfind("."):
                cleaned = num_str.replace(".", "").replace(" ", "").replace(",", ".")
            else:
                cleaned = num_str.replace(",", "").replace(" ", "")
        else:
            cleaned = num_str.replace(" ", "").replace(".", "")
        try:
            amount = float(cleaned)
            if amount >= 100:
                amounts.append(int(amount))
        except ValueError:
            continue

    return max(amounts) if amounts else None


def decide_route(email: IncomingEmail, c: Classification) -> Optional[str]:
    if c.welfare_signals:
        return "urgent_welfare"
    if c.category in ALWAYS_ESCALATE:
        return f"category:{c.category.value}"
    if c.language == Language.OTHER:
        return "language_not_supported"
    if c.category == Category.DONATION:
        amount = detect_donation_amount(email.body)
        if amount and amount >= DONATION_ESCALATION_THRESHOLD_NOK:
            return f"large_donation:{amount}_nok"
    if c.category == Category.GENERAL and c.confidence == "low":
        return "unclassified_low_confidence"
    return None


# ============================================================================
# Step 4 — Load context
# ============================================================================

def load_drafter_context(category: Category) -> str:
    core = load_core_context()
    cat_specific = load_category_context(category.value, CATEGORY_TO_KB_FILES)
    live = load_live_context()  # sheet-synced current schedules/events
    parts = [core] + [p for p in (cat_specific, live) if p]
    return "\n\n".join(parts)


# ============================================================================
# Step 5 — Draft
# ============================================================================

DRAFTER_SYSTEM_PROMPT = """You are an email drafter for Hope Spot Organization \
(HSO), a Norwegian humanitarian NGO based in Trondheim. Your job is to draft \
warm, dignified, practical replies to incoming emails.

You will be provided with HSO's voice/tone, background, escalation rules, a \
do-not-say list, category-specific FAQ content, the email classification, \
and the original email. Use ALL of this context. The voice and tone document \
is especially important.

# Your output

Produce ONLY the body of a draft email reply. No subject line, no preamble.

# Reply language

Reply in the language detected by the classifier:
- norwegian → Bokmål
- english → English
- arabic → Arabic
- ukrainian → Ukrainian
- other → output exactly: [ESCALATE: language not supported]

# Thread context

If earlier messages in the thread are provided, you are drafting the NEXT \
reply in an ongoing conversation, not a first response:
- Do not repeat information already given earlier in the thread
- Do not re-introduce HSO or greet as if for the first time
- Stay consistent with what was already said (by HSO staff or by earlier \
drafts) — if something earlier now seems wrong, escalate instead of \
contradicting it
- If the conversation has moved beyond what the KB covers, escalate with \
[ESCALATE: conversation beyond KB scope]

# Voice

- Warm without saccharine; dignified, never pitying
- Clear, practical, plain language; short sentences
- Honest and direct; never oversell
- Concise — typical target 100-300 words

Open with the recipient's name if known. Sign off with "the Hope Spot team" \
or appropriate language equivalent. Do not invent staff names.

# Self-check

1. Does this email actually fit the category? If not: [ESCALATE: classification mismatch — <reason>]
2. Anything that should escalate but wasn't routed there? If yes: [ESCALATE: <reason>]
3. Critical info missing from context? If yes: [ESCALATE: missing information — <what>]

If any check fails, output the ESCALATE marker. Do not draft a partial reply.

# NEVER

- Legal advice or interpretation of immigration cases
- Medical or mental health advice
- Promises of specific outcomes
- References to specific HSO staff by name (unless explicitly in context)
- References to specific community members by name
- Religious language
- Political statements
- Inflated claims
- Pity language
- Made-up facts about programs, schedules, or services
- Email/phone/address other than HSO's main contact info

If you don't have specific info, do NOT invent. Use general phrasing or escalate.
"""


def draft_reply(email: IncomingEmail, c: Classification) -> tuple[str, int]:
    context = load_drafter_context(c.category)

    history_section = ""
    if email.thread_history:
        history_section = (
            "# === EARLIER MESSAGES IN THIS THREAD (oldest first) ===\n\n"
            f"{email.thread_history}\n\n"
        )

    user_message = f"""\
{context}

# === EMAIL CLASSIFICATION ===

Language: {c.language.value}
Category: {c.category.value}
Confidence: {c.confidence}

{history_section}# === EMAIL TO REPLY TO ===

From: {email.sender_name} <{email.sender_email}>
Subject: {email.subject}

{email.body}

---

Now produce your draft, following all rules in the system prompt.
"""

    response = call_model(
        model=MODEL_DRAFTER,
        system_prompt=DRAFTER_SYSTEM_PROMPT,
        user_message=user_message,
        max_tokens=800,
        temperature=0.3,
    )

    return response.content.strip(), response.tokens_used


# ============================================================================
# Step 6 — Self-check parse
# ============================================================================

ESCALATE_PREFIX_RE = re.compile(r"^\s*\[ESCALATE:\s*(.+?)\]\s*", re.IGNORECASE)


def parse_drafter_output(output: str) -> tuple[Optional[str], Optional[str]]:
    match = ESCALATE_PREFIX_RE.match(output)
    if match:
        return None, match.group(1).strip()
    return output, None


# ============================================================================
# Main entry point
# ============================================================================

def process_email(email: IncomingEmail) -> AgentResult:
    started = datetime.now(timezone.utc)

    skip_reason = should_skip(email)
    if skip_reason:
        return AgentResult(
            outcome=Outcome.SKIPPED,
            email_message_id=email.message_id,
            skip_reason=skip_reason,
            latency_ms=int((datetime.now(timezone.utc) - started).total_seconds() * 1000),
        )

    try:
        classification = classify_email(email)
        total_tokens = classification.tokens_used
        _, classifier_model_id = resolve_model(MODEL_CLASSIFIER)
        cost = estimate_cost_usd(classifier_model_id, classification.tokens_used)

        escalation_reason = decide_route(email, classification)
        if escalation_reason:
            return AgentResult(
                outcome=Outcome.ESCALATED,
                email_message_id=email.message_id,
                classification=classification,
                escalation_reason=escalation_reason,
                total_tokens=total_tokens,
                estimated_cost_usd=cost,
                latency_ms=int((datetime.now(timezone.utc) - started).total_seconds() * 1000),
            )

        draft_output, draft_tokens = draft_reply(email, classification)
        total_tokens += draft_tokens
        _, drafter_model_id = resolve_model(MODEL_DRAFTER)
        cost += estimate_cost_usd(drafter_model_id, draft_tokens)

        draft_body, drafter_escalation = parse_drafter_output(draft_output)
        if drafter_escalation:
            return AgentResult(
                outcome=Outcome.ESCALATED,
                email_message_id=email.message_id,
                classification=classification,
                escalation_reason=f"drafter:{drafter_escalation}",
                total_tokens=total_tokens,
                estimated_cost_usd=cost,
                latency_ms=int((datetime.now(timezone.utc) - started).total_seconds() * 1000),
            )

        return AgentResult(
            outcome=Outcome.DRAFTED,
            email_message_id=email.message_id,
            classification=classification,
            draft_body=draft_body,
            total_tokens=total_tokens,
            estimated_cost_usd=cost,
            latency_ms=int((datetime.now(timezone.utc) - started).total_seconds() * 1000),
        )

    except ModelError as e:
        logger.error("Model error processing %s: %s", email.message_id, e)
        return AgentResult(
            outcome=Outcome.ERROR,
            email_message_id=email.message_id,
            error_message=f"model_error: {e}",
            latency_ms=int((datetime.now(timezone.utc) - started).total_seconds() * 1000),
        )
    except Exception as e:
        logger.exception("Unexpected error processing %s", email.message_id)
        return AgentResult(
            outcome=Outcome.ERROR,
            email_message_id=email.message_id,
            error_message=str(e),
            latency_ms=int((datetime.now(timezone.utc) - started).total_seconds() * 1000),
        )


def process_email_from_dict(payload: dict) -> dict:
    email = IncomingEmail(
        message_id=payload["message_id"],
        thread_id=payload.get("thread_id", payload["message_id"]),
        sender_email=payload["sender_email"],
        sender_name=payload.get("sender_name", ""),
        subject=payload.get("subject", ""),
        body=payload.get("body", ""),
        has_attachments=payload.get("attachment_count", 0) > 0,
        attachment_count=payload.get("attachment_count", 0),
        thread_history=payload.get("thread_history", ""),
    )
    return process_email(email).to_dict()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    demo = IncomingEmail(
        message_id="demo-001",
        thread_id="demo-thread-001",
        sender_email="newcomer@example.com",
        sender_name="Ali",
        subject="Norwegian classes",
        body="Hi, I just moved to Trondheim from Iraq. My English is okay but my Norwegian is basic. Do you have classes I could join?",
    )
    print(json.dumps(process_email(demo).to_dict(), indent=2, default=str))
