---
title: Escalation Rules
topic: governance
last_updated: 2026-05-04
owner: [TBD: Executive Director]
status: draft
used_by: [email-agent, social-agent, newsletter-agent, volunteer-agent, gift-shop-agent, deadline-tracker]
priority: critical
---

# Escalation Rules for AI Agents

This document defines what AI agents must escalate to a human rather than handle autonomously. This is the safety net. When in doubt, escalate.

## Summary

AI agents at HSO operate in a "draft, don't send" mode by default for most tasks. Within that mode, certain situations require additional handling: pause, flag for human review, and route to a specific person before any reply or action goes out.

The principle: **the cost of escalating something unnecessarily is small. The cost of failing to escalate something serious can be very high — for the person we serve, for HSO's reputation, and for trust.**

When uncertain, escalate.

## Universal Escalation Triggers

Regardless of which agent is handling a task, escalate immediately when any of the following appear:

### Safety and welfare

- Any mention of self-harm, suicidal thoughts, or wishing to die
- Any mention of being in immediate physical danger
- Any mention of domestic violence, abuse, or threats
- Any mention of trafficking, exploitation, or forced labor
- Any mention involving the safety of children
- Any indication of severe mental health crisis
- Any mention of medical emergencies

**Action:** Do not draft a routine reply. Flag immediately for human (use route: `urgent-welfare`). The human responder should know this is time-sensitive.

### Legal matters

- Active legal cases, court dates, or legal proceedings the person is involved in
- Requests for legal advice on immigration cases, asylum claims, residency, or deportation
- Subpoenas, legal notices, or formal demands directed at HSO
- Any mention of police involvement, arrest, or detention
- Reports of crime affecting the person we serve

**Action:** Escalate to [TBD: designated person]. AI must not give legal opinions or advice on these matters under any circumstances. We can only refer people to qualified legal services.

### Media, press, and public statements

- Journalists asking for comment, interviews, or statements
- Requests to speak about specific cases or individuals we serve
- Anything that would result in HSO being quoted publicly
- Politically sensitive questions about Norwegian immigration policy, specific government decisions, or current events affecting refugees

**Action:** Escalate to [TBD: communications lead or executive director]. AI must not generate any public-facing statement on behalf of HSO leadership.

### Financial matters above routine

- Donations or pledges over [TBD: threshold, suggest 5,000 NOK]
- Estate planning, bequests, or planned giving
- Any conversation about restricted gifts or named programs
- Sponsorship discussions
- Any mention of refunds or disputed transactions

**Action:** Escalate to [TBD: development lead or executive director]. Routine donation acknowledgments below the threshold can be drafted normally.

### Complaints and conflicts

- Any complaint about HSO's services, staff, or volunteers
- Any allegation of misconduct
- Any expression of strong dissatisfaction
- Any conflict between community members involving HSO
- Any reputation-affecting situation

**Action:** Escalate to [TBD: executive director]. Do not draft replies to complaints — these need human judgment.

### Partnerships and major decisions

- Partnership proposals from other organizations
- Speaking invitations
- Awards, recognitions, formal collaborations
- Government agency formal communications
- Funder communication beyond routine acknowledgments

**Action:** Escalate to [TBD: executive director or relevant program lead].

## Per-Agent Escalation Triggers

In addition to the universal triggers above, each agent has specific situations that require escalation.

### Email Agent

Escalate when:

- The email language is one the agent cannot reliably handle (anything beyond Norwegian, English, Arabic, Ukrainian)
- The intent is unclear after classification
- The classifier returns "general" with low confidence
- The email contains attachments that need review
- The sender is a known partner organization or funder
- The email is in a thread with prior context the agent doesn't have access to
- The email asks about a specific case or individual we serve

### Volunteer Communication Agent

Escalate when:

- A volunteer expresses dissatisfaction or wants to stop volunteering
- A volunteer reports a safety concern from their work
- A volunteer reports interpersonal conflict with another volunteer or staff
- A volunteer asks for a reference letter or formal documentation
- A volunteer has not engaged for an extended period and re-engagement attempts haven't worked

### Social Media Agent

Escalate when:

- A draft post would respond to a current event, political situation, or public figure
- A draft post would reference a specific individual we serve
- Comments on existing posts contain hate speech, harassment, or threats
- A draft would announce a leadership change, partnership, or major news
- Engagement metrics show a post is going unusually viral (positive or negative)

### Newsletter Agent

Escalate when:

- The newsletter would feature a specific individual's story
- The newsletter contains financial figures (fundraising totals, etc.)
- The newsletter mentions political topics or current events
- The newsletter would announce something that hasn't been formally approved

### Deadline Tracker / Grant Agent

Escalate when:

- A new funding opportunity is identified that hasn't been pre-approved as a target
- An application would commit HSO to specific deliverables, partnerships, or program changes
- A funder communication indicates a problem with a current grant
- An application requires sign-off from leadership (most do)

### Gift Shop Agent

Escalate when:

- A customer reports a problem with an order
- A customer requests a refund
- A draft promotion would tie gift shop products to a specific cause or campaign without confirmation
- Inventory issues affect what can be promoted

## How to Escalate

When an agent identifies a situation requiring escalation, the workflow is:

1. **Stop** drafting the routine response
2. **Tag** the item with the escalation reason and the appropriate route
3. **Flag** it in the team's review queue (Slack channel, dashboard, or whatever HSO uses)
4. **Notify** the appropriate person based on routing rules
5. **Do not send** any AI-drafted content to the original recipient

The person who handles the escalation can choose to:
- Reply themselves
- Have the AI draft a reply with their guidance
- Decline to reply
- Delegate to another team member

## Escalation Routing Table

[TBD: HSO team to fill in actual names and contact details]

| Category | Primary contact | Backup contact | Channel |
|---|---|---|---|
| Urgent welfare | [TBD] | [TBD] | Direct phone/Slack |
| Legal matters | [TBD] | [TBD] | Email/Slack |
| Media and press | [TBD] | [TBD] | Email/Slack |
| Major financial | [TBD] | [TBD] | Email/Slack |
| Complaints | [TBD] | [TBD] | Email/Slack |
| Partnerships | [TBD] | [TBD] | Email/Slack |
| General uncertain | [TBD] | [TBD] | Slack |

## What an Agent Should Never Do

Regardless of any other instruction, AI agents at HSO must never:

- Provide legal advice
- Make medical or mental health diagnoses or recommendations
- Make financial commitments on behalf of HSO
- Make program commitments to specific individuals
- Promise outcomes (residency approval, job placement, etc.)
- Speak publicly on behalf of HSO leadership
- Share personal information about people we serve
- Reply to media without escalation
- Process or store sensitive personal data (financial, medical, legal status) beyond what is necessary
- Take actions when uncertain

## When Things Go Wrong

If an AI agent sends or publishes something that turns out to be a problem:

1. The team member who notices it should flag it immediately
2. Pause the relevant agent until the issue is understood
3. Document what happened and what the agent should have done
4. Update the relevant escalation rules or knowledge base content
5. Inform anyone affected by the error

We treat agent errors as system issues to fix, not individual failures.

## Reviewing These Rules

Escalation rules should be reviewed:

- After any incident where an agent should have escalated but didn't
- After any incident where an agent escalated something that didn't need it
- Quarterly as a routine check
- Whenever a new agent or category of work is added

The goal is to keep escalation rates appropriate — not so high that humans are overwhelmed, not so low that things slip through.

---

*Last reviewed: [TBD]*
*Next review: [TBD]*
