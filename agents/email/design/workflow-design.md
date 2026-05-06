# Email Agent Workflow Design

This document specifies the email agent's workflow as it runs in Make.com (or n8n / equivalent). Each step is a discrete module in the workflow.

## Workflow Overview

```
[Trigger]                  Gmail: New email watcher
    ↓
[Step 1]                   Filter: skip if from internal domain or auto-replies
    ↓
[Step 2]                   Classify: language + category + welfare signals
    ↓
[Step 3]                   Decision: should this auto-draft or escalate?
    ↓                       │
    │                       └─ If escalate → [Step 8 escalation path]
    ↓
[Step 4]                   Load knowledge base context (always-load + category-specific)
    ↓
[Step 5]                   Draft: generate reply via drafter prompt
    ↓
[Step 6]                   Check drafter output for [ESCALATE:] marker
    │                       │
    │                       └─ If escalation → [Step 8 escalation path]
    ↓
[Step 7]                   Create Gmail draft, apply [AI-DRAFT] label
    ↓
[Step 8]                   Log activity to Google Sheets
    ↓
[Step 9]                   Notify reviewer (Slack message or email)
    ↓
[End]
```

Escalation path bypasses Steps 4-7 and routes the email to the appropriate human queue with a tag indicating why.

## Step-by-Step Specification

### Trigger: Gmail Watch

**Module:** Gmail — Watch Emails

**Configuration:**
- Folder: INBOX
- Mark as read: No (let humans see they were processed)
- Maximum number of results: Process all
- Watch frequency: Every 5 minutes (configurable based on volume)

**Output:** New email object with sender, subject, body, headers, attachments info

### Step 1: Initial Filter

**Module:** Filter

**Skip the email if any of:**
- Sender domain is `hopespot.no` or contains `@hopespot` (internal)
- Sender is on the autoresponder/no-reply list (configurable)
- Subject contains "Auto-reply", "Out of office", "Delivery Failure"
- Email is in a thread the agent already responded to (track via Gmail thread ID in logs)
- Email has more than 3 attachments (likely a document submission, route to human)
- Email body is empty or under 10 characters

**For skipped emails:** Log them as "skipped" with the reason. Don't process further.

### Step 2: Classify

**Module:** HTTP Request → Claude API (or via OpenRouter)

**Configuration:**
- Endpoint: configurable (OpenRouter recommended for model flexibility)
- Model: A fast/cheap model — Claude Haiku, GPT-4o-mini, Gemini Flash
- Max tokens: 200
- Temperature: 0 (we want deterministic classification)
- System prompt: contents of `system-prompt-classifier.md`
- User message: the email body, optionally with subject line appended

**Output handling:**
- Parse the JSON response
- If parsing fails or returned category is invalid → set category to "general", confidence to "low", continue to step 3
- If classification succeeds → store {language, category, confidence, welfare_signals, notes}

**Logging:**
- Log the classification call: tokens used, latency, output
- This feeds into ongoing classifier quality monitoring

### Step 3: Routing Decision

**Module:** Router (Make.com) or Switch (n8n)

**Decision logic:**

```
If welfare_signals == true:
    → Route: ESCALATE_URGENT_WELFARE
    → Stop processing, jump to escalation path

Else if category in [media_press, funder_communication, complaint_or_concern]:
    → Route: ESCALATE_<category>
    → Stop processing, jump to escalation path

Else if category == "donation_enquiry" AND mentioned_amount > donation_threshold:
    → Route: ESCALATE_LARGE_DONATION
    → Stop processing, jump to escalation path

Else if language == "other":
    → Route: ESCALATE_LANGUAGE_NOT_SUPPORTED
    → Stop processing, jump to escalation path

Else if category == "general" AND confidence == "low":
    → Route: ESCALATE_UNCLASSIFIED
    → Stop processing, jump to escalation path

Else:
    → Continue to Step 4 (auto-draft path)
```

**Donation threshold detection:** Use a simple regex or a quick second model call to extract any monetary amount from the email. If detected and over threshold, escalate.

### Step 4: Load Knowledge Base Context

**Module:** Multiple Google Drive (or Notion API) reads, parallel where possible

**Always load (these go into static context):**
- `00_Core/voice-and-tone.md`
- `00_Core/about-hopespot.md`
- `00_Core/escalation-rules.md`
- `00_Core/do-not-say.md`

**Category-specific loads (based on category):**

| Category | Documents to load |
|---|---|
| services_enquiry | `02_FAQs/services.md`, `01_Programs/*` (relevant ones) |
| volunteer_enquiry | `02_FAQs/volunteering.md`, `04_Volunteers/lifecycle-stages.md` |
| donation_enquiry | `02_FAQs/donations.md` |
| gift_shop_enquiry | `02_FAQs/gift-shop.md`, `05_Gift_Shop/products.md` |
| partnership_enquiry | `02_FAQs/partnerships.md` |
| general | `02_FAQs/*.md` (all FAQs, agent picks what's relevant) |

**Optimization:** Cache file contents — these don't change often. Refresh cache daily or on file change webhook.

**Output:** Concatenated context string with clear section headers between documents.

### Step 5: Draft Reply

**Module:** HTTP Request → Claude API (or via OpenRouter)

**Configuration:**
- Endpoint: configurable (OpenRouter recommended)
- Model: A capable model — Claude Sonnet, Claude Opus, GPT-4-class
- Max tokens: 800
- Temperature: 0.3 (some variation in phrasing is fine; not too random)
- System prompt: contents of `system-prompt-drafter.md`
- User message: structured input containing:
  ```
  # Voice and Tone Guidelines
  [contents of voice-and-tone.md]
  
  # About HSO
  [contents of about-hopespot.md]
  
  # Escalation Rules
  [contents of escalation-rules.md]
  
  # Do Not Say
  [contents of do-not-say.md]
  
  # Category-Specific Context
  [loaded category-specific documents]
  
  # Email Classification
  Language: <detected language>
  Category: <category>
  Confidence: <confidence>
  
  # Original Email
  From: <sender name>
  Subject: <subject>
  
  Body:
  <email body>
  ```

**Use prompt caching** for the static context (voice, about, escalation, do-not-say). This reduces cost by ~80% for these tokens after the first call.

**Output:** Draft reply text (or `[ESCALATE: reason]` marker)

### Step 6: Check for Escalation Marker

**Module:** Filter / Conditional

**Logic:**

```
If draft starts with "[ESCALATE:":
    → Extract reason after the colon
    → Route to escalation path with this reason
    → Stop processing

Else:
    → Continue to Step 7
```

This is the drafter's safety net — if it found something during drafting that should escalate, it can stop here.

### Step 7: Create Gmail Draft

**Module:** Gmail — Create Draft

**Configuration:**
- To: original sender's address
- Subject: "Re: " + original subject (preserving thread)
- In Reply To: original message ID (preserves threading)
- Body: draft text from Step 5, plus appended signature
- Labels: `[AI-DRAFT]`, `[Category: <category>]`, `[Language: <language>]`

**Signature appended automatically:**

```
---

Hope Spot Organization (HSO)
Ringvålvegen 2, 7080 Heimdal, Norway
+47 944 44 714 | Hope.spot.org@gmail.com
hopespot.no

This draft was prepared by our AI assistant and reviewed by our team.
[Optional disclosure — leadership decision on whether to include]
```

**Output:** Gmail draft ID for logging

### Step 8: Log Activity

**Module:** Google Sheets — Add Row (or equivalent)

**Log entry fields:**

| Field | Source |
|---|---|
| timestamp | Workflow start time |
| email_id | Gmail message ID |
| thread_id | Gmail thread ID |
| sender | Original from address |
| subject | Original subject |
| language | From classifier |
| category | From classifier |
| confidence | From classifier |
| welfare_signals | From classifier |
| outcome | "drafted" or "escalated_<reason>" |
| draft_id | If drafted: Gmail draft ID |
| escalation_route | If escalated: which queue |
| classifier_tokens | Tokens used in classifier call |
| drafter_tokens | Tokens used in drafter call (if drafted) |
| classifier_cost_usd | Calculated cost |
| drafter_cost_usd | Calculated cost |
| total_latency_ms | End-to-end time |
| reviewer_action | Filled in later by reviewer (sent / edited_then_sent / discarded / further_escalated) |
| reviewer_action_time | Filled in later |
| edits_made | Filled in later (boolean or summary) |

**Two write phases:**
1. Initial write at end of automated workflow (steps 1-7)
2. Update when reviewer takes action (manual or via Gmail label change webhook)

### Step 9: Notify Reviewer

**Module:** Slack — Send Message (or Gmail / SMS / whatever team uses)

**Recipient:** [TBD: configurable — likely a #ai-drafts channel in Slack, plus DM to designated reviewer]

**Message format:**

For successful drafts:
```
📧 New AI-drafted email ready for review

From: <sender name> <<sender email>>
Subject: <subject>
Category: <category> | Language: <language> | Confidence: <confidence>

Open in Gmail: <link to draft>

Quick action: Approve as-is | Edit | Discard | Escalate further
```

For escalations:
```
⚠️ Email needs human attention — agent did not draft

From: <sender name> <<sender email>>
Subject: <subject>
Reason: <escalation reason>

Open in Gmail: <link to email>
Suggested route: <urgent_welfare | media | complaint | etc.>
```

**Urgency:**
- urgent_welfare → Priority notification (DM to designated welfare contact + backup)
- media_press → Notify communications lead
- funder_communication → Notify development lead
- Others → Standard notification

## Escalation Path Specification

When any step routes to escalation, this branch runs:

```
[Receive email + escalation reason]
    ↓
[Tag email in Gmail with appropriate label]
    ├─ [ESCALATE-URGENT-WELFARE]
    ├─ [ESCALATE-MEDIA]
    ├─ [ESCALATE-COMPLAINT]
    ├─ [ESCALATE-FUNDER]
    ├─ [ESCALATE-LARGE-DONATION]
    ├─ [ESCALATE-LANGUAGE]
    └─ [ESCALATE-UNCLASSIFIED]
    ↓
[Add to escalation tracking sheet/dashboard]
    ↓
[Send urgent notification based on category]
    ↓
[Log in main activity log with outcome = "escalated_<reason>"]
```

No draft is created. No reply is sent. The email sits in the inbox with the appropriate label until a human handles it.

## Error Handling

**API failures (model timeout, rate limit):**
- Retry once with exponential backoff
- If second attempt fails, log the failure and escalate the email to "general queue with API error"
- Notify ops if API failures exceed [TBD: threshold] per hour

**Knowledge base file not found:**
- Log warning
- Continue with available context (skip the missing file)
- If a critical file (voice, about) is missing, halt the workflow and notify ops

**Gmail draft creation failure:**
- Retry once
- If fails, output the draft text into the activity log so the reviewer can copy/paste manually
- Notify ops

**Logging failure:**
- Workflow continues — never block on logging
- Use a dead-letter queue for failed log entries
- Reconcile periodically

## Performance Targets

- **End-to-end latency:** Target < 30 seconds from email arrival to draft ready (95th percentile)
- **Throughput:** Should comfortably handle 100 emails/day (HSO's likely volume) with room for 10x growth
- **Cost:** Target < $50/month at typical volume — much lower with prompt caching

## Configuration Variables

These should be configurable without code changes:

- `MODEL_CLASSIFIER`: which model to use for classification (default: claude-haiku via OpenRouter)
- `MODEL_DRAFTER`: which model to use for drafting (default: claude-sonnet via OpenRouter)
- `DONATION_ESCALATION_THRESHOLD_NOK`: amount above which donations escalate (default: 5000)
- `REVIEWER_NOTIFICATION_CHANNEL`: where to send draft notifications
- `URGENT_WELFARE_CONTACTS`: list of people to notify for welfare situations
- `KB_REFRESH_INTERVAL_MINUTES`: how often to refresh cached KB content (default: 60)

## Testing Plan

Before going live:

**Unit tests (manual or scripted):**
- Run classifier on 50+ past emails of known category. Measure accuracy.
- Run drafter on 20 sample emails. Have humans rate quality 1-5.
- Test all escalation paths trigger correctly with synthetic examples.
- Test language detection on emails in each supported language.
- Test edge cases: empty body, very long body, attachments, threads, replies to existing threads.

**Integration tests:**
- End-to-end run on 10 sample emails. Verify drafts appear in Gmail with correct labels.
- Verify activity log captures all expected fields.
- Verify reviewer notifications go to the right channels.

**Soft launch:**
- Run on 20% of incoming emails for one week. Compare outcomes to humans handling the rest.
- Adjust based on what surfaces.

**Full launch:**
- Run on all incoming emails in draft mode.
- Daily review of metrics for first month.
