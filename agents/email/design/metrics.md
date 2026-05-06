# Email Agent — Metrics

This document defines what to measure for the email agent and how to use those measurements to improve it over time.

## Why Measure

Three reasons:

1. **Demonstrate value** to leadership — concrete numbers on hours saved, response time improvements, volume handled
2. **Catch quality issues early** — if the agent's drafts are degrading, metrics show it before it becomes a visible problem
3. **Drive improvements** — patterns in the metrics tell us what to fix

The metrics framework should be light enough that nobody dreads reviewing it. Aim for a 15-minute weekly check.

## Metrics

### Operational Metrics

These measure that the system is running properly.

**Volume:**
- Emails processed per day / week / month
- Emails per category
- Emails per language
- Skipped emails (filtered before processing)

**Latency:**
- End-to-end time from email arrival to draft ready (target: < 30 seconds at 95th percentile)
- Classifier latency (target: < 3 seconds)
- Drafter latency (target: < 15 seconds)

**Reliability:**
- API failure rate (target: < 1%)
- Workflow completion rate (target: > 99%)
- Errors per day

**Cost:**
- Total API spend per week / month
- Cost per email processed
- Cost breakdown by classifier vs. drafter

### Quality Metrics

These measure how good the agent's output actually is.

**Approval rate:**
- % of drafts sent without significant edits
- % sent with minor edits (under ~20% changed)
- % sent with major edits (over ~20% changed)
- % discarded entirely

Significance of "edits" is judgment — for v1, just track sent/edited/discarded as a three-way split. Later, add granularity if useful.

**By category:**
- Approval rate per category (e.g., services_enquiry approval rate, volunteer_enquiry approval rate)
- Categories with consistently high approval are candidates for less review or auto-send
- Categories with low approval need KB or prompt improvements

**By language:**
- Approval rate per language
- Norwegian and English likely high; Arabic and Ukrainian may need more review initially

**Escalation rates:**
- % of emails escalated vs. drafted
- Escalations by reason
- "False escalations" — situations escalated that humans determined didn't actually need to escalate
- "Missed escalations" — drafts sent that humans believe should have been escalated

A healthy escalation rate balances: too low and serious things slip through; too high and humans are overwhelmed. Target 5-15% escalation rate, but watch the *content* of escalations — better to escalate something unnecessary than miss something serious.

### Time and Productivity Metrics

These measure the value HSO is getting.

**Response time:**
- Average time from email received to reply sent
- Compared to baseline (pre-agent response time, if measurable)
- % of emails replied to same-day, next-day, within-week

**Time saved:**
- Estimated minutes saved per drafted email (human estimate, e.g., "this would have taken me 10 minutes to write from scratch")
- Total hours saved per week
- Calculated value (hours saved × hourly cost)

**Coverage:**
- % of incoming emails getting any AI involvement (drafted, escalated, or otherwise processed)
- Pre-agent baseline: % of emails getting timely replies
- Post-agent: % of emails getting timely replies

### Learning Metrics

These help improve the system over time.

**Edit patterns:**
- What kinds of edits do reviewers make most often? Categories:
  - Tone adjustments (sounds too formal/casual)
  - Factual corrections (got something wrong)
  - Length adjustments (too long/short)
  - Specifics added (filled in details the agent didn't have)
  - Structure changes (reorganized)
- Recurring edits in one direction → update prompt or KB

**Knowledge base gaps:**
- When agent had to use general phrasing because specific info wasn't available
- Recurring questions where the answer wasn't in the KB
- Information humans had to add to drafts

**Classifier accuracy:**
- When the classifier got the category wrong (caught by reviewer or by drafter's escalation)
- Patterns in misclassifications (e.g., partnership emails being classified as general)

**Reviewer feedback:**
- A simple "rate this draft" mechanism in Gmail/Slack — thumbs up/down or 1-5
- Free-text notes from reviewers on what was good or bad
- Aggregated weekly

## Measurement Setup

### Data Sources

1. **Activity log** (Google Sheets / Airtable): captures every workflow run with all the fields specified in `workflow-design.md`
2. **Reviewer actions** (manual or via Gmail label monitoring): tracks what humans did with each draft
3. **API usage logs** (from OpenRouter or model providers): cost and latency data
4. **Reviewer feedback** (Slack reactions, Google Form, or note field): qualitative input

### Dashboard

A simple dashboard pulls these together. Options:

**Lightweight:** A second Google Sheet that aggregates the activity log into pivot tables and charts. Updated daily via Make.com workflow. Free, simple, sufficient for HSO scale.

**Moderate:** Looker Studio (formerly Data Studio) connected to the Google Sheets. Better visualization, still free, slightly more setup.

**Heavier:** A custom dashboard (Retool, simple web app). More flexibility but maintenance overhead. Probably not worth it for HSO scale.

**Recommendation:** Start with the lightweight Google Sheets dashboard. Upgrade only if there's a clear need.

### Review Cadence

**Daily (5 min, just for the first 4 weeks):**
- Spot-check a few drafts. Are they good?
- Any escalations that look concerning?
- Any errors in the workflow?

**Weekly (15 min, ongoing):**
- Total volume processed
- Approval rate
- Categories with low approval — anything to investigate?
- Hours saved estimate
- Cost trend

**Monthly (1 hour, ongoing):**
- Full metrics review
- Knowledge base gap analysis (what info do we keep needing to add?)
- Edit pattern analysis (what do reviewers consistently change?)
- Decision points: do we adjust thresholds, prompts, or processes?

**Quarterly (half-day, ongoing):**
- Deep review with leadership
- Model comparison (test current setup against newer models)
- Prompt updates and re-testing
- Escalation rules review

## What to Do With the Metrics

Metrics aren't just for reporting — they should drive actions.

**Trigger: Approval rate drops below 80% on a specific category**
- Action: Review recent drafts in that category. Is it the prompt, the KB content, or something about the emails themselves changing?

**Trigger: Latency spikes above target**
- Action: Check API status. Consider switching models temporarily if one provider is degraded.

**Trigger: Cost grows faster than volume**
- Action: Check token usage per call. Has the KB grown too large? Are documents being loaded that shouldn't be?

**Trigger: Reviewers consistently make the same edit**
- Action: Update the prompt or KB to incorporate the change. Re-test on past emails.

**Trigger: Escalations from a particular reason consistently turn out to not need escalation**
- Action: Refine the escalation rule or classifier prompt to reduce false positives.

**Trigger: A new category of email starts appearing**
- Action: Classify it manually for a few weeks. If volume justifies it, add it as a formal category with its own KB content.

## Reporting to Leadership

Monthly summary for leadership should include:

1. **Headline numbers:** Emails handled, response time improvement, hours saved
2. **Quality:** Approval rate trend, any incidents
3. **Cost:** Spend vs. budget
4. **Issues:** Anything to be aware of, anything that needs leadership input
5. **What's coming:** Planned improvements, next agent deployment, etc.

Keep it short. One page. Two charts maximum.

## Privacy and Data Handling

Metrics must respect privacy:

- Don't log full email content in metrics (it's in the activity log for debugging, but with restricted access)
- Aggregate metrics shouldn't expose individual senders
- Be especially careful with welfare-flagged emails — these need extra access controls
- GDPR considerations: HSO operates in Norway/EU. Personal data in logs has retention and access requirements

[TBD: Confirm with HSO data protection approach. May need to consult on GDPR compliance specifically for the email logs.]
