# HSO AI Agent System — What Leadership Needs to Know

This document is for HSO leadership and team members. It explains what the AI agent system does, what it doesn't do, and what's expected of HSO.

## What we're building

A set of AI assistants that help with the most time-consuming repetitive work, so the team has more time for the people HSO serves.

We identified six pain points:

1. Replying to email enquiries
2. Volunteer communication
3. Monthly newsletter
4. Social media content creation
5. Missing application deadlines
6. Gift shop advertisement

We're building one agent per pain point, starting with email enquiries (highest volume) and grant deadline tracking (highest financial impact).

## What an "agent" is

Think of each agent as a careful, well-trained assistant who:

- Reads the relevant content
- Drafts a response in HSO's voice
- Knows when to escalate to a human
- Never sends anything without human approval (in the initial deployment)

The agents use AI under the hood, but they work within strict guidelines: a voice and tone document, a list of things never to say, escalation rules for sensitive situations. They are not free-form chatbots — they are focused tools doing specific tasks.

## What the agents will NOT do

This is just as important as what they will do.

**They will not send anything automatically.** Every reply, post, or message starts as a draft for HSO to review. After several weeks of consistent quality, certain low-risk categories may graduate to auto-send — but always with HSO leadership approval.

**They will not make decisions for HSO.** Partnerships, complaints, media requests, large donations, anything sensitive — these always go to a human.

**They will not invent facts.** If an agent doesn't have specific information (a class schedule, a policy detail), it uses general phrasing or escalates. We've designed the system to fail honestly rather than confidently bullshit.

**They will not handle welfare situations.** If someone reaches out in crisis, the agent flags it immediately for human attention. It does not try to help directly.

**They will not replace anyone.** They reduce the time spent on repetitive tasks. The relationship work, the judgment calls, the actual help to people — all of that remains human.

## What HSO leadership needs to do

The agents need ongoing input from HSO to work well:

### Initial setup (one-time, ~4-6 hours of leadership time)

- Verify and fill in the knowledge base (programs, schedules, fees, eligibility, partners) — see `updating-the-kb.md`
- Confirm the voice and tone document represents HSO accurately
- Confirm escalation rules and routing (who gets notified for what)
- Designate reviewers for AI drafts

### Ongoing (about 30 min per week of leadership time)

- Review agent activity (the activity log spreadsheet)
- Update the knowledge base when programs change
- Approve or adjust escalation thresholds based on what comes through
- Quarterly review with the AI maintainer

### When the agent gets something wrong

- Don't panic — every error is fixable
- Note what happened in the shared notes
- The maintainer will update the relevant prompt or knowledge base content
- Use the "draft, don't send" pattern to catch issues before they go out

## What this costs

At HSO's expected volume:

- AI usage costs: $5-15/month
- Hosting infrastructure: $0-15/month
- Total ongoing: under $50/month

Plus maintenance time from whoever's running this for HSO.

## What this saves

Realistic estimates based on HSO's described pain points:

- Email replies: 5-10 hours/week saved (assuming 30+ enquiries handled)
- Newsletter: 1 day/month saved
- Social media: 1 day/week saved
- Volunteer comms: 2-3 hours/week saved
- Grant deadlines: at least one missed grant prevented per year (which can be many thousands of NOK)

We'll track real numbers once each agent is live.

## What can go wrong (and what we do about it)

**The agent says something inappropriate.** The "draft, don't send" pattern catches this. Reviewers see it before it goes out. We update the prompt or knowledge base to prevent it next time.

**The agent misses a sensitive situation.** This is the most serious risk. The escalation rules are conservative on purpose — better to escalate too much than too little. We track this carefully and adjust.

**The AI provider has an outage.** The system uses OpenRouter as a gateway, which provides automatic fallbacks. If one provider is down, another picks up.

**Costs grow unexpectedly.** We monitor costs weekly. The system can be paused at any time. There's no contractual commitment to keep it running.

**The maintainer becomes unavailable.** The codebase, knowledge base, and documentation are all in HSO's repository. Another developer can pick it up. Documentation is written with this scenario in mind.

## What's locked in vs. flexible

**Not locked in:**
- The AI model — we can swap from Claude to GPT to Gemini to a self-hosted model with one configuration change
- The orchestration platform — Make.com or n8n or custom code, we can switch
- The hosting provider — Render, Fly.io, anywhere
- The maintainer — anyone with development skills can take over

**Locked in:**
- Nothing structural

This is intentional. HSO should be able to take this in any direction in the future without being trapped.

## Questions and concerns

Concerns from HSO leadership are welcome at any time. The system is designed to be paused, modified, or shut down if something feels wrong. There is no "we have to keep this running" pressure.

Common questions:

**"How do we know it's saying the right thing?"**
We review every draft for the first weeks. After consistent quality, leadership decides which categories are safe enough to graduate.

**"What if it sends something embarrassing?"**
It won't — the draft-only pattern means humans are the last step. Auto-send is graduated only to safe categories with leadership approval.

**"Is this private? Are emails leaving HSO's control?"**
Email content is sent to the AI provider for processing. This is unavoidable — the AI needs to read the email to respond. Choose providers carefully (OpenRouter, Anthropic, OpenAI all have privacy policies; some have BAAs and EU data residency options). For maximum privacy, a self-hosted model is possible. Discuss tradeoffs with the maintainer.

**"What about GDPR?"**
HSO operates in Norway/EEA. The system needs a data flow diagram and privacy assessment. Activity logs intentionally avoid storing full email content. Retention can be limited. The maintainer can help build a GDPR-compliant deployment.

**"What if our needs change?"**
The system is built modular. Adding agents, removing agents, changing agents — all are normal operations, not rebuilds.

## Where things are

- The repository (code + knowledge base): [TBD: GitHub URL]
- The activity log spreadsheet: [TBD]
- The Slack workspace for AI notifications: [TBD]
- The webhook deployment: [TBD]
- The maintainer's contact: [TBD]

## Next checkpoints

Each phase has a moment where leadership decides to proceed:

1. **After initial setup** — leadership reviews the knowledge base content, approves the voice document, signs off on escalation rules. This is essentially "is the AI representing HSO correctly on paper?"
2. **After soft launch (1 week)** — leadership reviews real drafts the agent produced for real emails. Decides whether to proceed to full launch.
3. **Monthly during operation** — leadership reviews metrics, costs, and quality. Decides whether to expand, adjust, or pause.
4. **Per new agent** — same approval process for each subsequent agent (deadline tracker, newsletter, etc.).

No agent goes live without a clear go-ahead from HSO.
