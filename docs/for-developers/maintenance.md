# Maintenance Guide

For the developer (you, future you, or your replacement) running this system for HSO.

## Cadence

### Daily — first 4 weeks after each agent goes live

5 minutes:
- Check the latest activity log entries — anything weird?
- Check the webhook server health (Render/Fly dashboard)
- Glance at any escalations from the day before

### Weekly — ongoing

15 minutes:
- Total volume processed per agent
- Approval rate (drafts sent vs. drafts edited vs. drafts discarded)
- Categories with low approval — what's going wrong?
- Hours saved estimate
- API cost trend

### Monthly — ongoing

1 hour:
- Full metrics review
- Knowledge base gap analysis: what info do we keep needing to add?
- Edit pattern analysis: what do reviewers consistently change?
- Decision points: do we adjust thresholds, prompts, or processes?
- Send leadership the monthly summary

### Quarterly — ongoing

Half a day:
- Deep review with HSO leadership
- Cross-provider model comparison (test current setup against newer/cheaper models)
- Prompt updates and re-testing
- Escalation rules review
- Plan next agent or improvements

## Common operations

### Add a new FAQ category

1. Decide if it warrants a new agent category or is a subset of existing
2. Add a new file in `kb/02_FAQs/`
3. If it's a new email category, add it to:
   - `Category` enum in `agents/email/agent.py`
   - `CATEGORY_TO_KB_FILES` mapping in same file
   - Classifier prompt examples
   - `agents/email/design/categories.md`
   - Test fixtures
4. Run tests
5. Test against real samples
6. Deploy

### Update a prompt

1. Edit the prompt in `agents/<agent>/agent.py`
2. Run offline tests: `python tests/test_<agent>_pipeline.py`
3. Run real-sample test against current production model:
   ```
   python agents/<agent>/run_cli.py --folder tests/sample_emails/
   ```
4. If significant change, run against an alternate provider too (model portability)
5. Commit with description of what changed and why
6. Deploy

### Swap models

1. Update env var in deployment platform (Render dashboard, Fly secrets, etc.)
2. Restart the service
3. Watch the next few drafts carefully
4. Compare metrics over the following week
5. If quality degrades, revert (one env var change)

### Investigate a bad draft

1. Find the email's row in the activity log
2. Look at: classification, escalation reason, draft body, edits made
3. Re-run that email through the agent locally:
   ```
   python agents/<agent>/run_cli.py --email <copy of email JSON>
   ```
4. Identify which step went wrong: classifier? router? drafter? KB content?
5. Fix the appropriate place
6. Add a test case to prevent regression

### Investigate a missed escalation

This is the highest-priority class of issue. Drop other work.

1. Find the email
2. Confirm the agent did NOT escalate when it should have
3. Look at classifier output — was the welfare/sensitive signal missed?
4. Look at the drafter's self-check output
5. Update either:
   - Classifier examples (add this case as a positive example for the right category)
   - Welfare keyword list (in `classify_email`)
   - Drafter self-check prompt
6. Add a test case
7. Tell HSO leadership what happened and what changed

### Roll out a new agent

1. Read `CONTRIBUTING.md` "Adding a new agent" section
2. Build the agent following the email agent's structure
3. Soft launch with HSO leadership review
4. Add to the README status table
5. Document in `docs/for-hso/<new-agent>.md`

### Pause an agent in an emergency

If something is going seriously wrong (e.g. agent producing inappropriate drafts, costs spiking unexpectedly):

1. **In Make.com / n8n:** disable the workflow. Drafts stop being created immediately.
2. **In the webhook server:** can also be paused by stopping the deployment.
3. Investigate without time pressure
4. Communicate with HSO that the agent is paused and why
5. Resume when fixed

## Cost monitoring

Cost data lives in the activity log. Pull it monthly to chart:

- Total spend per agent per month
- Cost per email/post/draft
- Cost trend over time

If costs spike:
- Check if KB content has grown (more context = more tokens)
- Check if model selection changed
- Check for misuse (spike in volume could indicate spam reaching the inbox)
- Check for retry storms (transient failures triggering many calls)

Anthropic prompt caching, when enabled, reduces costs ~80% for static context. Worth turning on once volume justifies it.

## When something is broken

Order of operations when production looks broken:

1. **Triage:** is it intermittent or consistent? Affecting some agents or all? Is it a deployment issue (server down) or a behavior issue (server up but bad output)?
2. **Logs:** webhook server logs in Render/Fly + activity log spreadsheet + Make/n8n execution logs. Match timestamps.
3. **Local repro:** can you reproduce locally with a sample email? Most issues become obvious once reproduced.
4. **Fix:** code, prompt, or config change.
5. **Test:** run the test suite, then run real samples.
6. **Deploy.** Watch the next batch carefully.
7. **Document:** if it's a class of issue that could happen again, add a test case and a note in the relevant prompt or KB.

## Things not to do

**Don't fix bugs by adding more rules to prompts.** When prompts grow rule-by-rule from each issue, they become brittle and hard to swap models for. Prefer fixing in the KB or in code structure.

**Don't add provider-specific code outside `shared/model_gateway.py`.** Same reason as above — protects model portability.

**Don't store full email bodies in logs.** GDPR matters. Metadata only.

**Don't auto-graduate categories to auto-send.** Always with HSO leadership approval, always after multiple weeks of consistent quality data.

**Don't let infrastructure work dominate.** It's tempting to build elaborate observability, fancy frameworks, complex routing. The goal is value to HSO. Aim for 80% delivery, 20% infrastructure.

## When to bring HSO leadership in

Reach out to leadership for:

- Anything affecting their reputation (a draft that almost went out, an escalation pattern that suggests we're missing things)
- Cost surprises (bigger than ±20% from expected)
- Decisions about graduating categories to auto-send
- Decisions about adding agents or changing escalation rules
- Major model swaps (not minor model updates within same provider)
- New funder, new program, new audience type — these affect the KB significantly
- Anything that feels uncomfortable

Don't bring leadership in for: routine bugs, minor prompt tweaks, internal refactors, dependency updates.

## Handoff readiness

The codebase, KB, and docs are written so anyone with development skills could pick this up. To stay ready for handoff:

- Keep `docs/for-developers/` current as you change things
- Document any operational quirks or one-off decisions
- Make sure secrets are documented in `.env.example` (without values, obviously)
- Make sure the README's "Quick Start" actually works for someone new

Once a year, do a "stranger test" — read the docs as if you were new to the project. Note what's confusing. Fix it.
