# How to Update the Knowledge Base

This guide is for HSO team members who need to update the content the AI agents read when responding to emails, drafting posts, and so on.

You don't need any technical skills to update the knowledge base — it's just markdown text files.

## Why the knowledge base matters

The AI agents are only as good as the information they have access to. If the knowledge base says "Norwegian classes meet on Tuesdays at 18:00" and that's wrong, the agent will tell people the wrong thing.

If the knowledge base doesn't have information about a topic, the agent will use general phrasing or escalate to a human — which is fine, but means you're handling more questions personally than necessary.

**Investment in the knowledge base pays off in time saved on every email.**

## Where the knowledge base lives

[TBD: depends on chosen storage. Options:]
- A folder in HSO's Google Drive
- A Notion workspace
- A Git repository (managed by the maintainer)

Whichever option, you'll work with markdown (.md) files.

## What's in there

```
kb/
├── 00_Core/                  ← The big four — read by every agent
│   ├── voice-and-tone.md     ← How HSO talks
│   ├── about-hopespot.md     ← Who HSO is, what we do
│   ├── escalation-rules.md   ← When the agent must escalate
│   └── do-not-say.md         ← Hard limits on agent content
├── 01_Programs/              ← One file per program
├── 02_FAQs/                  ← Common questions by topic
│   ├── services.md
│   ├── volunteering.md
│   ├── donations.md
│   └── ...
├── 03_Funders_Grants/        ← Funder profiles
├── 04_Volunteers/            ← Volunteer info
├── 05_Gift_Shop/             ← Products, campaigns
└── 06_Templates/             ← Reusable response patterns
```

## The most important documents

**voice-and-tone.md** — Defines how HSO talks. If the agent's drafts don't sound like HSO, this is usually where to look.

**about-hopespot.md** — Background on HSO. The agent uses this for any context about who we are and what we do.

**escalation-rules.md** — When the agent must escalate to a human. If the agent is over- or under-escalating things, this is where to adjust.

**do-not-say.md** — Hard limits. Things the agent must never produce.

**02_FAQs/*.md** — Specific topical content. Usually the most edited files.

## How to update a file

### Simple text changes

Just edit the file. Save. Done.

The next time the agent processes an email that uses this content, it'll see your update.

If it's stored in Git, the maintainer (or you, if you have access) commits the change. If it's in Google Drive or Notion, just save normally — the agent re-reads files automatically.

### Updating the metadata

Every file has a section at the top that looks like this:

```yaml
---
title: Services FAQ
topic: services
last_updated: 2026-05-04
owner: [TBD: Communications Lead]
status: draft
used_by: [email-agent]
priority: high
---
```

When you make a substantive change, update `last_updated` to today's date.

If the change is significant or you want it reviewed before it affects agent behavior, change `status` from `approved` to `under_review`. The agent will skip documents that aren't approved.

Once reviewed, change it back to `approved`.

### Adding a new FAQ entry

Open the relevant FAQ file (e.g. `02_FAQs/services.md`) and add a new question/answer section using the same format as existing entries:

```markdown
### Question I want to add

Answer in 2-4 sentences. Direct, conversational, in HSO's voice. Include any relevant URLs or addresses.
```

The agent picks up new entries automatically.

### Adding a whole new file

If you have a new topic that doesn't fit existing files (e.g. a new program with its own FAQs), create a new file in the relevant folder. Use an existing file as a template.

If the file is for a new agent or category that's not yet handled, talk to the maintainer — they'll wire it into the system.

## Common things to update

**Class schedules.** When the Norwegian class schedule changes, update `02_FAQs/services.md`. This is probably the most-changed content.

**Event information.** Coming events go in social media content; recurring program events go in the FAQ files.

**Office hours.** If hours change, update both `02_FAQs/services.md` and `00_Core/about-hopespot.md`.

**Fees and eligibility.** If anything changes about who can use what services, update the relevant FAQ file.

**Volunteer opportunities.** New roles, schedule changes, requirements — `02_FAQs/volunteering.md`.

**Donation processes.** PayPal links, recurring options, tax info — `02_FAQs/donations.md`.

**Partner organizations.** Referral lists in the FAQs (e.g. "for legal questions, see NOAS").

## What to escalate to the maintainer

You don't need to ask the maintainer for routine content updates. But please flag:

- Adding a whole new agent category (e.g. "we need to handle [new type] of email")
- Changes that affect escalation rules (who gets notified for what)
- Changes that might affect privacy or data handling
- Something that's confusing and you're not sure how to update
- Discovering the agent has been giving wrong information for a while (we should look at why)

## Tips

**Keep it conversational.** The agent reads your text and uses it as context. If your text sounds bureaucratic, the agent's drafts will too. If your text sounds warm and clear, the drafts will too.

**Use real examples.** Adding "Example: Someone asks X, we say Y" is the most powerful way to teach the agent. Examples beat rules.

**Be specific.** "Classes are sometimes in the evening" is less useful than "Beginner classes are Mondays and Wednesdays at 18:00."

**Note what's uncertain.** It's fine to write "[TBD: confirm before this goes live]" when you're drafting. Just remember to fill it in.

**Update one thing at a time.** Big rewrites are harder to review and easier to break. Small edits are safer.

## The voice and tone document deserves its own care

If you ever update `00_Core/voice-and-tone.md`, think of it as updating HSO's brand voice. Every agent uses this, every draft, everywhere. Take a moment to read your changes aloud and ask "is this how we want everyone to perceive HSO?"

## What if I make a mistake?

Nothing you can do here will break the system. Worst case:

- The agent might draft a few messages with stale or wrong info before you fix it (and reviewers should catch this)
- If you accidentally delete a file, ask the maintainer — Git keeps history (or the file is in Google Drive's trash)

Don't be afraid to edit. The knowledge base only stays useful if it's updated regularly.
