# Contributing to HSO AI

Conventions and patterns for working on this codebase. Read this before making changes — these aren't arbitrary; they protect the design.

## The non-negotiables

These are the rules that protect HSO's interests:

### 1. Never break the model abstraction

All LLM calls go through `shared/model_gateway.py`. **No exceptions.**

If you find yourself wanting to write `import anthropic` or `requests.post("https://api.openai.com/...")` in agent code, stop. Add what you need to the gateway instead.

This protects HSO's ability to swap providers, which is the most important architectural property of the system.

### 2. Never invent facts in prompts

Prompts must instruct models to escalate or use general phrasing when specific information isn't available, rather than making things up. The "do not say" KB document and explicit prompt instructions enforce this.

When you find a prompt producing made-up info, the fix is usually:
- Add the missing info to the KB, or
- Strengthen the "don't invent" instruction with a specific example

Never solve hallucination by adding more rules to the prompt indefinitely. The cleaner fix is richer context.

### 3. Always escalate when uncertain

False positives on escalation are acceptable. False negatives — failing to escalate something serious — are not. When in doubt about whether to escalate, the answer is yes.

### 4. Draft mode is the default

Agents create drafts; humans send them. Auto-send is graduated to per-category over time, only after consistent quality data and only with HSO leadership approval. Don't shortcut this.

### 5. Never commit secrets or real user data

The `.gitignore` covers `.env.local` and other obvious targets. But real email content, real funder names, real volunteer info — these don't belong in the repo. Use `[TBD]` placeholders, sample fixtures with fake data, and aggregate metrics only.

## Repo conventions

### Where things live

- `shared/` — code multiple agents use
- `agents/<name>/` — per-agent code, design docs, prompts
- `kb/` — markdown knowledge base
- `tests/` — tests + fixtures
- `workflows/` — Make.com / n8n exports
- `docs/for-hso/` — documentation HSO leadership reads
- `docs/for-developers/` — technical documentation
- `deploy/` — deployment configs (Render, Fly, etc.)
- `scripts/` — operational scripts (one-off tooling, migrations)

### Naming

- Python files: `snake_case.py`
- Markdown files: `kebab-case.md`
- Test files: `test_<thing>.py`
- KB files: `kebab-case.md` with YAML frontmatter

### Imports

Agent code imports from `shared/` like this:

```python
from shared.model_gateway import call_model
from shared.kb_loader import load_core_context
```

The `_PROJECT_ROOT` path manipulation at the top of agent files makes this work whether you run them as scripts or modules.

### Type hints

Use them. Especially on dataclasses and module-level functions.

```python
def process_email(email: IncomingEmail) -> AgentResult:
    ...
```

### Logging vs printing

Use `logging` for anything in the runtime path. Reserve `print` for CLI scripts.

```python
logger = logging.getLogger(__name__)
logger.info("Processed email id=%s outcome=%s", id_, outcome)
```

## Development workflow

### Before changing anything

1. Read the relevant agent's `design/` folder — it explains the why, not just the what
2. Read this CONTRIBUTING.md if you haven't recently
3. Run the tests and confirm they pass: `python tests/test_email_pipeline.py`

### Making a change

1. Make the change
2. Run the tests: `python tests/test_email_pipeline.py`
3. If you changed prompt logic, run a real-sample test against at least 2 providers (see `docs/for-developers/model-portability.md`)
4. Update relevant docs (especially if behavior changed)
5. Commit with a clear message that says what changed and why

### Adding a new agent

1. Read at least one existing agent's design docs end-to-end
2. Create `agents/<new>/` with the same file structure
3. Write the design docs FIRST (categories, prompts, workflow) before any code
4. Use `shared/` modules for everything you can
5. Add tests in `tests/test_<new>_pipeline.py` with sample fixtures
6. Add the agent to the README's status table

### Updating the knowledge base

If you're adding or significantly changing KB content:

1. Edit the markdown files in `kb/`
2. Update the `last_updated` field in the frontmatter
3. If the change is substantive, set `status: under_review` until reviewed
4. Once approved, set `status: approved`
5. Commit

The agents only use docs with `status: approved` (in production mode). Drafts don't drive agent behavior.

### Working with prompts

Prompts are version-controlled like code. To change a prompt:

1. Edit the prompt in the agent's Python file (or its `design/` doc if it lives there)
2. Test against the sample emails — does behavior change as expected?
3. If the change is significant, test across at least two providers
4. Document the change in commit message — what changed, why, and how it was tested

Avoid rewriting prompts in big-bang changes. Iterate in small steps.

## Things to avoid

### Premature abstraction

If you find yourself building infrastructure that no current agent uses, ask: do we have a real second agent that needs this? If not, defer. The abstraction will be cleaner once you've seen the second use case.

### Provider-specific features in core paths

Anthropic's prompt caching, OpenAI's structured outputs, Gemini's massive context — all useful, all optional. They go behind the model gateway abstraction, not in agent logic.

### Heavy frameworks before they're needed

LangChain, LangGraph, CrewAI etc. are useful for genuinely complex agents. The current agents don't need them. Don't bring them in until there's a specific agent that benefits.

### Logging email content

Activity logs capture metadata (sender, category, outcome). They should not store full email body. GDPR matters, and Norway is in the EEA.

## Questions

When in doubt, prefer:

- Simplicity over cleverness
- Existing patterns over new ones
- Tested code over claimed-to-work code
- Documented behavior over implicit knowledge
- Small commits over large ones
- Real data points over speculation

The maintainer's job is to keep this simple enough that it can be handed off to someone else if needed. Code that feels too clever to explain is probably too clever.
