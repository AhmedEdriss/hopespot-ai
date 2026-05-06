# HSO Knowledge Base

This is the foundation of HSO's AI agent system. The documents here are the source of truth that AI agents reference when generating content, replying to communications, and supporting HSO's work.

## How This Works

AI agents need context to produce good work. This knowledge base provides that context in a structured, agent-readable form. When an email arrives or a social post is needed, the relevant document(s) get pulled into the agent's context, and the agent uses them to do its job in HSO's voice with HSO's facts.

## Folder Structure

```
HSO Knowledge Base/
├── 00_Core/                  ← Used by every agent
│   ├── voice-and-tone.md     ← How HSO communicates
│   ├── about-hopespot.md     ← Who HSO is, what we do
│   ├── escalation-rules.md   ← When to involve a human
│   └── do-not-say.md         ← Hard limits on AI content
│
├── 01_Programs/              ← Each program in its own file
│   └── [TBD]
│
├── 02_FAQs/                  ← Common questions by category
│   └── [TBD]
│
├── 03_Funders_Grants/        ← Funder profiles, application templates
│   └── [TBD]
│
├── 04_Volunteers/            ← Volunteer info, lifecycle templates
│   └── [TBD]
│
├── 05_Gift_Shop/             ← Products, campaigns, brand guidelines
│   └── [TBD]
│
└── 06_Templates/             ← Reusable response patterns
    └── [TBD]
```

The numbered prefix on each folder helps maintain consistent ordering. The `00_Core/` folder is special — those four documents are loaded into every agent's context. Everything else is loaded on demand based on what the task requires.

## Document Format

Every document follows the same structure:

1. **YAML frontmatter** at the top — metadata about the document (last updated, owner, status, which agents use it, priority)
2. **Title** as an H1 heading
3. **Summary** — 2-3 sentences explaining what this document covers
4. **Body content** — the actual information, organized with clear headers
5. **Edge cases / escalation** where relevant
6. **Related documents** as links
7. **Examples** wherever they help

This consistency is intentional — it makes documents predictable for both humans and AI agents to work with.

## Status Field

Every document has a `status` field in its frontmatter:

- `draft` — Under development, not yet approved for agent use
- `under_review` — Being reviewed by HSO leadership
- `approved` — Active and being used by agents

**AI agents should only use documents with `status: approved`.** This is a safety mechanism — drafts in progress shouldn't accidentally drive agent behavior.

## Maintenance

The knowledge base is alive. It only stays useful if it stays current.

**Recommended cadence:**

- **Weekly (15 min):** Anyone can flag content that needs updating in a shared channel or doc
- **Monthly (1 hour):** Knowledge base owner reviews flagged items and stale documents (`last_updated` over 6 months)
- **Quarterly (half-day):** Full review — what's missing? What's never used? What are agents getting wrong?

**Triggers for immediate updates:**

- A program changes, is added, or is removed
- Office address, phone, or email changes
- A new partnership of significance
- A leadership change
- An incident where an agent got something wrong because of outdated content

## How to Add a New Document

1. Decide which folder it belongs in (or create a new one if needed — but use the existing structure when possible)
2. Use the document template format (see existing documents in `00_Core/` as reference)
3. Set status to `draft` initially
4. Get review from the document owner
5. Update status to `approved` once reviewed
6. Note in the relevant agent's instructions that this document exists

## How to Update an Existing Document

1. Edit the document
2. Update the `last_updated` field in the frontmatter
3. If changes are significant, set status back to `under_review` until approved
4. Note major changes in the document's history (or rely on git/version history if applicable)

## Working in Multiple Languages

The knowledge base itself is maintained in English (working language for the project). Translations to Norwegian, Arabic, Ukrainian, or other languages happen at the agent output level — i.e., the agent reads English context and produces output in the target language.

For some content (like specific Norwegian phrasing or culturally-specific examples), source content may be in Norwegian. That's fine; consistency within a document is more important than consistency across the whole base.

## What This Knowledge Base Is Not

- **Not a wiki for general HSO information.** It's specifically structured for AI agent consumption. Other HSO documents (employee handbook, financial records, etc.) live elsewhere.
- **Not a substitute for human judgment.** The escalation rules document defines when humans must step in.
- **Not static.** It will evolve with HSO's work and with each agent we build.

## Questions or Issues

[TBD: Designated KB owner contact]
