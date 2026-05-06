# Setup Guide — Production Deployment

This guide walks through deploying the email agent to production. Allow about half a day of focused work.

## Prerequisites

- Admin access to HSO's Gmail account (Hope.spot.org@gmail.com)
- A computer with Python 3.10+
- A credit card or payment method for OpenRouter (~$10 starting credit is plenty)
- A place to host the webhook (free options: Render, Fly.io, Railway, Google Cloud Run)
- Slack workspace (optional but recommended) or another notification channel
- Google account for the activity log spreadsheet

If using Make.com or n8n:
- Make.com or n8n account (free tiers work for low volume)

## Step 1: Get an OpenRouter API key

1. Sign up at https://openrouter.ai/
2. Add $10-20 in credit (will last months at HSO's volume)
3. Create an API key from the dashboard
4. Save it somewhere secure — you'll set it as `OPENROUTER_API_KEY`

OpenRouter gives you access to Claude, GPT, Gemini, and many other models through one API. You can switch which model the agent uses by changing the model name in environment variables, no code changes.

## Step 2: Set up the knowledge base

The KB folder (`hopespot-kb/`) must be accessible to the webhook server. Two approaches:

**Option A — Bundle the KB with the deployment.**
Copy the KB folder into your deployment package. Simple, but you redeploy every time content changes.

**Option B — Mount KB from external storage.**
Store the KB in Google Drive, S3, or a Git repo. Webhook fetches content as needed. More flexible but more setup.

For HSO's scale and likely update frequency, Option A is fine. The webhook can be redeployed in minutes.

**Before going live, complete the `[TBD]` items in:**
- `00_Core/about-hopespot.md` — programs, partners, leadership names
- `00_Core/escalation-rules.md` — the routing table with real names
- `02_FAQs/services.md` — actual schedules, fees, eligibility
- `02_FAQs/volunteering.md` — orientation schedule, role descriptions
- `02_FAQs/donations.md` — tax-deductibility, receipt process

Once filled in, change each document's `status: draft` to `status: approved` in the frontmatter.

## Step 3: Deploy the Python webhook

Pick one of these hosting options. All have free tiers.

### Option A — Render.com (recommended for simplicity)

1. Sign up at https://render.com
2. Create a new "Web Service"
3. Connect to a Git repo containing the `python/` folder, or use Render's manual deploy
4. Set:
   - Build command: `pip install -r requirements.txt`
   - Start command: `gunicorn webhook_server:app --bind 0.0.0.0:$PORT`
5. Add environment variables:
   - `OPENROUTER_API_KEY` = your OpenRouter key
   - `HSO_KB_PATH` = `./hopespot-kb` (and include the KB folder in your deploy)
   - `HSO_WEBHOOK_SECRET` = generate a long random string (used to authenticate Make/n8n calls)
   - `HSO_MODEL_CLASSIFIER` = `anthropic/claude-haiku-4.5` (or your preferred classifier model)
   - `HSO_MODEL_DRAFTER` = `anthropic/claude-sonnet-4.6` (or your preferred drafter model)
6. Deploy. You'll get a URL like `https://hso-agent.onrender.com`
7. Verify it's working: visit `https://hso-agent.onrender.com/healthz` — should return `{"healthy": true, ...}`

Note: also `pip install gunicorn` should be added to requirements.txt if using gunicorn as the production server.

### Option B — Fly.io

Similar setup. Use `fly launch` from the `python/` folder. Set the same env variables via `fly secrets set`.

### Option C — Google Cloud Run

Deploy as a container. Set env variables in the Cloud Run service config.

### Option D — Run on a VM you already have

If HSO has a server, just run the webhook with a process manager (systemd, supervisor, pm2). Make sure it's reachable from the internet (or use a tunnel like Cloudflare Tunnel for security).

## Step 4: Set up Gmail labels

In Gmail, create these labels (Settings → Labels → Create new):

**For drafts:**
- `AI-DRAFT`
- `Cat-services_enquiry`
- `Cat-volunteer_enquiry`
- `Cat-donation_enquiry`
- `Cat-gift_shop_enquiry`
- `Cat-partnership_enquiry`
- `Cat-general`
- `Lang-norwegian`
- `Lang-english`
- `Lang-arabic`
- `Lang-ukrainian`

**For escalations:**
- `ESCALATE-urgent_welfare`
- `ESCALATE-media_press`
- `ESCALATE-funder_communication`
- `ESCALATE-complaint_or_concern`
- `ESCALATE-large_donation`
- `ESCALATE-language_not_supported`
- `ESCALATE-unclassified`

These let humans filter the inbox and find what needs attention.

## Step 5: Set up the activity log

Create a Google Sheet called "HSO Email Agent Log" with these columns in row 1:

```
timestamp | message_id | thread_id | sender | subject | language | category | confidence | welfare_signals | outcome | draft_id | reason | tokens | cost_usd | latency_ms | reviewer_action | edits_made
```

Note the spreadsheet ID from the URL — you'll need it for Make/n8n configuration.

The first 15 columns are filled by the workflow. The last 2 (`reviewer_action`, `edits_made`) are filled in manually or via a separate workflow when humans act on drafts.

## Step 6: Set up Slack notifications (or alternative)

**If using Slack:**

1. Create a channel `#ai-drafts` for routine draft notifications
2. Create a channel `#ai-escalations` for non-urgent escalations
3. Create a channel `#ai-urgent` for welfare escalations (with mobile notifications enabled for relevant people)
4. Create a channel `#ai-ops` for errors

In Make/n8n, you'll need a Slack bot/app installed in your workspace — instructions vary by platform but are well-documented.

**If not using Slack:**

You can use email instead — have the workflow send notifications to designated email addresses. Less ideal for urgent welfare situations, but workable.

## Step 7: Choose orchestrator and import workflow

### If using Make.com

1. Sign up at https://make.com (or log in)
2. Create a new scenario
3. Click the "..." menu → Import Blueprint → upload `make/blueprint.json`
4. Make.com will warn about missing connections — that's expected
5. Configure each module:
   - Click each module that has a "REPLACE_WITH_*" placeholder
   - Set up the Gmail connection (OAuth flow)
   - Set up the Google Sheets connection
   - Set up the Slack connection
   - Configure the HTTP module with your webhook URL and secret
6. Test with a single email
7. Activate the scenario

### If using n8n

1. Set up n8n (cloud at https://n8n.cloud or self-hosted)
2. Click Workflows → Import → upload `n8n/workflow.json`
3. n8n will show errors for missing credentials — expected
4. Configure each node:
   - Set up the Gmail OAuth credential
   - Set up the Google Sheets credential
   - Set up the Slack credential
   - Configure the HTTP Request node with your webhook URL and secret
5. Test with a single execution
6. Activate the workflow

## Step 8: Test end-to-end

Send yourself a test email to Hope.spot.org@gmail.com (from a different account):

```
Subject: Norwegian classes
Body: Hi, I'm new to Trondheim. When do your Norwegian classes meet?
```

Within 5 minutes, you should see:

1. The workflow runs in Make/n8n (visible in their UI)
2. A new draft appears in Gmail with the `AI-DRAFT` label
3. A notification in your Slack `#ai-drafts` channel
4. A new row in the activity log spreadsheet

Review the draft. Did the agent capture HSO's voice? Is the information accurate? Edit if needed and send.

If anything goes wrong, check:
- The webhook server's logs (Render/Fly dashboard)
- The Make/n8n execution log
- The Google Sheets log for what was recorded

## Step 9: Soft launch

Run on real incoming emails for one week. During this week:

- Review every draft before sending
- Note where you edit drafts and why
- Note any escalations that should have been drafts (or vice versa)
- Track the metrics from `email-agent/metrics.md`

After a week, hold a review:
- What's the approval rate?
- Are any categories systematically problematic?
- Does the KB need updates?
- Are escalation rules correct?

## Step 10: Full launch

Once soft launch shows good quality, all incoming emails get an AI draft. Continue reviewing every one until approval rates are consistently high (>90% sent without significant edits across all common categories).

After 4-6 weeks, consider graduating specific high-confidence categories to auto-send. The decision to auto-send any category should involve HSO leadership, not just the implementer.

## Ongoing Maintenance

**Weekly (15 min):**
- Check the metrics dashboard
- Spot-check a few drafts for quality
- Note any KB gaps surfaced

**Monthly (1 hour):**
- Update KB content based on the month's gaps
- Review edit patterns from reviewers
- Check API costs are on track

**Quarterly (half-day):**
- Full review with HSO leadership
- Test current setup against newer/cheaper models
- Update voice and tone document if needed
- Plan next agent (volunteer comms, newsletter, etc.)

## Common Issues

**Drafts in the wrong language**
The classifier got the language wrong. Check the activity log for what was detected. Usually the email had mixed languages or unusual phrasing. Add an example to the classifier prompt to handle the case.

**Drafts inventing facts**
The drafter made up information not in the KB. Either add the missing info to the KB, or strengthen the "don't invent" rule in the drafter prompt with the specific case.

**Too many escalations**
The escalation thresholds are too sensitive. Review which escalations turned out to be unnecessary and adjust the rules.

**Webhook timeouts**
If model calls take too long, the webhook may time out. Increase timeout in the orchestrator (Make/n8n) and on the webhook server.

**API rate limits**
At HSO's volume this is unlikely, but if you hit it, OpenRouter will tell you. Either upgrade your OpenRouter plan or add retry/backoff logic.

**Costs higher than expected**
Check the activity log for tokens used. If high per email, the KB may have grown too large or context is being loaded that shouldn't be. Review the routing table.

## Security Notes

- The webhook secret prevents random callers from invoking the agent. Keep it secret.
- The OpenRouter API key has spending power — don't commit it to Git, don't share.
- The activity log contains email content — restrict access to the sheet to authorized HSO staff only.
- If using Render/Fly.io, enable HTTPS (they do by default).
- Consider GDPR implications of logged email content. You may want to:
  - Limit log retention (delete logs after 90 days)
  - Avoid logging full email bodies (only metadata)
  - Document the data flow for HSO's privacy policy

## Getting Help

- OpenRouter docs: https://openrouter.ai/docs
- Make.com docs: https://make.com/help
- n8n docs: https://docs.n8n.io
- Render docs: https://render.com/docs

The Python code in `python/agent.py` is heavily commented — most questions can be answered by reading it.
