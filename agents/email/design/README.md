# Email Agent — Overview and Architecture

This folder contains the design and prompts for HSO's email agent — the system that drafts replies to incoming email enquiries.

## What This Agent Does

The email agent watches HSO's main inbox (Hope.spot.org@gmail.com) for incoming messages. For each message, it:

1. Detects the sender's language
2. Classifies the email's intent
3. Pulls relevant context from the knowledge base
4. Drafts a reply in the sender's language using HSO's voice
5. Places the draft in Gmail (does NOT send it)
6. Notifies a human reviewer that a draft is ready

A human reviews every draft before it goes out. After 4-6 weeks of consistent quality, certain low-risk categories may graduate to auto-send.

## What This Agent Does Not Do

- Reply to anything categorized as media, complaint, funder communication, or welfare-related — these always escalate to a human
- Send any email automatically (in the initial deployment)
- Engage with attachments — those route to a human
- Handle threads with prior context the agent can't see — escalate
- Reply in languages outside Norwegian, English, Arabic, Ukrainian — escalate

## Architecture

The agent is a 9-step pipeline orchestrated by Make.com (or n8n). Each step is a discrete action, and the agent can stop at any step (escalate, log, exit) based on what it finds.

```
[1] Email arrives in Gmail
[2] Language detection
[3] Intent classification  
[4] Escalation check
[5] Context loading from knowledge base
[6] Draft generation
[7] Self-check on draft
[8] Create Gmail draft (tagged [AI-DRAFT])
[9] Log activity + notify reviewer
```

See `workflow-design.md` for the detailed workflow specification.

## Files in This Folder

- `README.md` (this file) — overview
- `workflow-design.md` — detailed step-by-step workflow specification
- `system-prompt-classifier.md` — prompt for the classification step
- `system-prompt-drafter.md` — prompt for the drafting step
- `categories.md` — the email categories with escalation rules
- `routing-table.md` — which knowledge base documents load for each category
- `metrics.md` — what to measure and how

## Models Used

The agent uses two model calls per email:

**Classifier:** A fast, cheap model (Haiku, GPT-4o-mini, or similar via OpenRouter). The task is pure classification — short input, single-word output.

**Drafter:** A capable model (Claude Sonnet or equivalent). The task requires nuanced writing in HSO's voice across multiple languages.

Both calls go through OpenRouter so models can be swapped via configuration.

## Approval Pattern

This agent operates in **draft-only mode**. Every output requires human review before sending. The pattern:

1. Agent creates draft
2. Draft sits in Gmail with `[AI-DRAFT]` label
3. Human reviewer (configurable: comms lead, ED, designated reviewer) gets notified
4. Reviewer either:
   - Approves and sends (one click)
   - Edits and sends (most common in the early phase)
   - Discards
   - Escalates further

Each reviewer action is logged. Edits are particularly valuable — they show where the agent's drafts need improvement.

## Success Metrics

See `metrics.md` for the full list. Key metrics:

- **Coverage:** % of incoming emails the agent successfully drafts (vs. escalates or fails)
- **Approval rate:** % of drafts sent without significant edits
- **Edit rate:** Average amount of text changed before sending
- **Time saved:** Estimated hours saved per week vs. manual replies
- **Response time:** Time from email arrival to reply sent (with AI vs. without)

## Rollout Plan

**Week 1-2:** Build and configure. Test on a small set of past emails (use last month's enquiries as a test set).

**Week 3:** Soft launch. Agent runs on real incoming emails but only on a sample (e.g., 1 in 5 emails get a draft, others handled manually). Compare quality.

**Week 4:** Full launch in draft mode. Agent drafts replies for every incoming email; humans review and send.

**Week 8+:** Review approval rate by category. Categories with consistently high approval rates (>90% sent without significant edits) become candidates for auto-send. Decisions on auto-send are made by leadership, not by metrics alone.

## Maintenance

The agent's quality depends on the knowledge base it draws from. Maintenance focuses on:

- **Updating FAQ content** when the agent gets things wrong or outdated info appears
- **Tracking edit patterns** — if reviewers consistently edit drafts in similar ways, that's a signal to update the prompts or the knowledge base
- **Updating escalation rules** if new situations emerge that should escalate but don't
- **Adding new categories** if recurring email types don't fit existing categories

Quarterly review by the comms lead and the agent owner. Monthly metrics check.

## What to Do When Things Break

**Agent stops drafting:** Check Make.com workflow status. Most common cause is API rate limits or knowledge base file access issues.

**Agent drafts something problematic:** Don't send it. Document what happened. Update the relevant prompt or knowledge base content. Consider whether the situation should have escalated.

**Reviewers can't keep up:** Add reviewers, or graduate trusted categories to auto-send sooner.

**Volume spikes:** The agent scales with API usage. Watch costs but don't worry about rate limits unless email volume is unusually high.
