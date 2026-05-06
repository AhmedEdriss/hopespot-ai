"""
Email Agent — Pipeline tests.

Runs all sample emails through the agent in offline mode (mocked provider).
Catches integration issues, schema problems, and routing bugs without
spending API budget.

Run:
    python tests/test_email_pipeline.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Make agent + shared modules importable.
HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
sys.path.insert(0, str(PROJECT_ROOT))

from agents.email import agent, run_cli  # noqa: E402
from shared import model_gateway  # noqa: E402


# ============================================================================
# Expected outcomes per sample email
# ============================================================================

EXPECTATIONS = {
    "01_services_norwegian": {"outcome": "drafted", "category": "services_enquiry", "language": "norwegian"},
    "02_volunteer_english": {"outcome": "drafted", "category": "volunteer_enquiry", "language": "english"},
    "03_services_arabic": {"outcome": "drafted", "category": "services_enquiry", "language": "arabic"},
    "04_services_ukrainian": {"outcome": "drafted", "category": "services_enquiry", "language": "ukrainian"},
    "05_donation_small": {"outcome": "drafted", "category": "donation_enquiry", "language": "norwegian"},
    "06_donation_large": {"outcome": "escalated", "escalation_contains": "large_donation"},
    "07_media_press": {"outcome": "escalated", "escalation_contains": "media_press"},
    "08_urgent_welfare": {"outcome": "escalated", "escalation_contains": "urgent_welfare"},
    "09_funder_communication": {"outcome": "escalated", "escalation_contains": "funder_communication"},
    "10_complaint": {"outcome": "escalated", "escalation_contains": "complaint"},
    "11_autoreply": {"outcome": "skipped"},
}


# ============================================================================
# Smart mock provider — keyword-based routing for offline tests
# ============================================================================

class SmartMockProvider(model_gateway.Provider):
    """Mock provider that produces realistic outputs based on keywords."""
    name = "mock"

    def is_configured(self) -> bool:
        return True

    def call(self, model_id, system_prompt, user_message, max_tokens, temperature):
        # Heuristic: max_tokens<=200 means classifier; otherwise drafter.
        if max_tokens <= 200:
            return self._classify(user_message, model_id)
        return self._draft(model_id)

    def _classify(self, user_message: str, model_id: str) -> model_gateway.ModelResponse:
        text = user_message.lower()

        welfare_keywords = [
            "scared", "i am scared", "cannot leave", "took my passport",
            "hurting myself", "nowhere to go", "trapped", "abuse",
            "tells me what to do",
        ]
        is_welfare = any(k in text for k in welfare_keywords)

        # Language detection
        if any(c in user_message for c in "ابتةجدذرزسش"):
            language = "arabic"
        elif any(c in user_message for c in "абвгдежзий"):
            language = "ukrainian"
        elif any(w in text for w in [
            " hei", "norskkurs", "tusen takk", "frivillig", "imdi",
            "rapporteringsfrist", "tilskudd", "donere", "donasjon",
            "lurer på", "vil gjerne", "månedlig",
        ]):
            language = "norwegian"
        else:
            language = "english"

        # Category detection
        if is_welfare:
            category = "urgent_welfare"
        elif any(w in text for w in ["journalist", "interview", "aftenposten", "newspaper", "media"]):
            category = "media_press"
        elif any(w in text for w in ["disappointed", "rude", "very upset", "complaint"]):
            category = "complaint_or_concern"
        elif any(w in text for w in ["imdi", "tilskudd", "grant", "rapporteringsfrist", "funder"]):
            category = "funder_communication"
        elif any(w in text for w in ["donate", "donasjon", "donation", "donere", "monthly gift", "recurring"]):
            category = "donation_enquiry"
        elif any(w in text for w in ["volunteer", "frivillig"]):
            category = "volunteer_enquiry"
        elif any(w in text for w in ["partner", "collaborate", "partnership"]):
            category = "partnership_enquiry"
        elif any(w in text for w in ["gift shop", "shipping", "product", "order"]):
            category = "gift_shop_enquiry"
        else:
            category = "services_enquiry"

        return model_gateway.ModelResponse(
            content=json.dumps({
                "language": language,
                "category": category,
                "confidence": "high",
                "welfare_signals": is_welfare,
                "notes": f"[mock] lang={language} cat={category}",
            }),
            tokens_used=150,
            model_used=model_id,
            provider=self.name,
            latency_ms=10,
        )

    def _draft(self, model_id: str) -> model_gateway.ModelResponse:
        return model_gateway.ModelResponse(
            content=(
                "[MOCK DRAFT — offline test mode]\n\n"
                "Hi, thanks for reaching out. We'd love to help — drop by "
                "our office in Heimdal anytime.\n\n— the Hope Spot team"
            ),
            tokens_used=400,
            model_used=model_id,
            provider=self.name,
            latency_ms=10,
        )


# ============================================================================
# Test runner
# ============================================================================

def install_mock() -> None:
    """Replace all providers with the smart mock for offline testing."""
    mock = SmartMockProvider()
    model_gateway.set_provider("openrouter", mock)
    model_gateway.set_provider("anthropic", mock)
    model_gateway.set_provider("openai", mock)
    model_gateway.set_provider("mock", mock)


def run_tests() -> int:
    install_mock()

    sample_folder = HERE / "sample_emails"
    if not sample_folder.exists():
        print(f"Sample emails folder not found: {sample_folder}")
        return 1

    passed = 0
    failed = 0
    failures: list[tuple[str, str]] = []

    for sample_file in sorted(sample_folder.glob("*.json")):
        name = sample_file.stem
        expected = EXPECTATIONS.get(name)
        if not expected:
            print(f"⚠  No expectations for {name} — skipping")
            continue

        email = run_cli.load_email_from_file(sample_file)
        result = agent.process_email(email)

        actual_outcome = result.outcome.value
        if actual_outcome != expected["outcome"]:
            failures.append((name, f"outcome: expected={expected['outcome']} actual={actual_outcome}"))
            failed += 1
            print(f"✗ {name}")
            continue

        if expected["outcome"] == "drafted":
            if not result.classification:
                failures.append((name, "expected classification, got none"))
                failed += 1
                print(f"✗ {name}")
                continue
            if "category" in expected and result.classification.category.value != expected["category"]:
                failures.append((name, f"category: expected={expected['category']} actual={result.classification.category.value}"))
                failed += 1
                print(f"✗ {name}")
                continue
            if "language" in expected and result.classification.language.value != expected["language"]:
                failures.append((name, f"language: expected={expected['language']} actual={result.classification.language.value}"))
                failed += 1
                print(f"✗ {name}")
                continue
            if not result.draft_body:
                failures.append((name, "expected draft body, got none"))
                failed += 1
                print(f"✗ {name}")
                continue

        elif expected["outcome"] == "escalated":
            if "escalation_contains" in expected:
                if expected["escalation_contains"] not in (result.escalation_reason or ""):
                    failures.append((
                        name,
                        f"escalation_reason: expected to contain "
                        f"'{expected['escalation_contains']}' "
                        f"actual='{result.escalation_reason}'",
                    ))
                    failed += 1
                    print(f"✗ {name}")
                    continue

        passed += 1
        suffix = ""
        if result.classification:
            suffix += f" / {result.classification.category.value}"
        if result.escalation_reason:
            suffix += f" / {result.escalation_reason}"
        print(f"✓ {name} → {actual_outcome}{suffix}")

    print("\n" + "=" * 60)
    print(f"PASSED: {passed}    FAILED: {failed}")
    print("=" * 60)

    if failures:
        print("\nFailures:")
        for name, reason in failures:
            print(f"  - {name}: {reason}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(run_tests())
