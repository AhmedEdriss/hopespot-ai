# HSO AI — Hope Spot Organization Agent System

A growing system of AI agents that help [Hope Spot Organization](https://hopespot.no), a Norwegian humanitarian NGO supporting refugees and immigrants in Trondheim. The agents reduce time spent on repetitive communication work — replying to enquiries, drafting newsletters, tracking grant deadlines — so the team can focus on the people they serve.

## Status

| Agent | Status |
|---|---|
| Email | ✅ Built, tested, awaiting deployment |
| Deadline tracker / grant agent | ⏳ Planned |
| Newsletter | ⏳ Planned |
| Social media | ⏳ Planned |
| Volunteer comms | ⏳ Planned |
| Gift shop marketing | ⏳ Planned |

## Architecture

This codebase is a **single repo with multiple agents that share common infrastructure.** All agents use:

- **`shared/model_gateway.py`** — provider-agnostic LLM access. The agents call into this; the gateway routes to OpenRouter, Anthropic, OpenAI, or any other provider via configuration. **Swapping models is a config change, not a code change.** See [model-portability.md](docs/for-developers/model-portability.md).
- **`shared/kb_loader.py`** — reads the markdown knowledge base. Centralizes caching, frontmatter parsing, and access control (only "approved" docs reach production agents).
- **`kb/`** — the knowledge base in markdown. HSO's voice, programs, FAQs, escalation rules. Used by every agent.

Each agent lives under `agents/<name>/` with its own `agent.py`, `webhook_server.py`, `run_cli.py`, and design docs.

```
hopespot-ai/
├── shared/                   ← Code every agent uses
│   ├── model_gateway.py      ← Swap models via env vars
│   └── kb_loader.py          ← Read the KB
├── kb/                       ← Knowledge base (markdown)
│   ├── 00_Core/              ← Voice, escalation, do-not-say (used by all agents)
│   └── 02_FAQs/              ← Topic-specific FAQs
├── agents/
│   └── email/                ← Email agent
│       ├── agent.py          ← Agent logic
│       ├── webhook_server.py ← HTTP wrapper for Make/n8n
│       ├── run_cli.py        ← Local testing
│       └── design/           ← Design docs (categories, prompts, workflow)
├── workflows/
│   ├── make/                 ← Make.com blueprints (importable JSON)
│   └── n8n/                  ← n8n workflows (importable JSON)
├── tests/
│   ├── sample_emails/        ← Test fixtures covering all categories
│   └── test_email_pipeline.py
├── docs/
│   ├── for-hso/              ← Plain-language docs for HSO staff
│   └── for-developers/       ← Technical docs
├── deploy/                   ← Deployment configs
├── scripts/                  ← Operational scripts (one-off tooling)
└── .github/workflows/        ← CI
```

## Quick Start

### 1. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 2. Run tests offline (no API key needed)

```bash
python tests/test_email_pipeline.py
```

You should see 11 tests pass — services in 4 languages drafted, sensitive categories escalated, auto-replies skipped.

### 3. Run the email agent against a sample email with a real model

```bash
cp .env.example .env.local
# Edit .env.local — set OPENROUTER_API_KEY at minimum
source .env.local

python agents/email/run_cli.py --demo
```

You'll see real model output for the demo email (~$0.01 cost).

### 4. Run the webhook server locally

```bash
python agents/email/webhook_server.py
# In another shell:
curl http://localhost:8080/healthz
```

## Model Portability

The system is designed to work with any LLM provider. By default it uses Claude via OpenRouter, but switching to GPT-4, Gemini, Llama, or any other model is a configuration change.

```bash
# Default (Claude via OpenRouter)
export HSO_MODEL_DRAFTER=openrouter:anthropic/claude-sonnet-4.6

# Switch to GPT-4
export HSO_MODEL_DRAFTER=openrouter:openai/gpt-4o

# Switch to Gemini
export HSO_MODEL_DRAFTER=openrouter:google/gemini-pro-1.5

# Use Anthropic API directly (no OpenRouter)
export ANTHROPIC_API_KEY=...
export HSO_MODEL_DRAFTER=anthropic:claude-sonnet-4.6

# Self-hosted via OpenAI-compatible endpoint (e.g. vLLM)
# (Add a custom provider in shared/model_gateway.py)
```

See [docs/for-developers/model-portability.md](docs/for-developers/model-portability.md) for the full strategy and tradeoffs.

## Working in this repo

If you're a developer or AI tool (e.g. Claude Code) working on this codebase:

1. Read [CONTRIBUTING.md](CONTRIBUTING.md) for conventions
2. Read the relevant agent's `design/` folder before making behavioral changes
3. Run tests before and after any change: `python tests/test_email_pipeline.py`
4. Follow the model-agnostic principle — never call a provider's API directly from agent code; always go through `shared/model_gateway.py`

## Working with HSO

HSO leadership shouldn't need to touch the code. They interact with the system through:

- The Gmail inbox (reviewing AI drafts)
- The activity log spreadsheet (seeing what the agents do)
- Slack notifications (knowing when something needs attention)
- The knowledge base (updating content — see [docs/for-hso/updating-the-kb.md](docs/for-hso/updating-the-kb.md))

For HSO-facing documentation, see `docs/for-hso/`.

## Costs

At HSO's expected volume:

- **Model API costs:** $1-15/month
- **Webhook hosting (Render free tier or similar):** $0-7/month
- **Make.com or n8n cloud:** $0-10/month
- **Total:** Well under $50/month

## License

[TBD — discuss with HSO before adding a license.]

## Maintainer

[TBD: your name and contact]

If this project is in active development, weekly maintenance includes:
- Reviewing the activity log for issues
- Updating KB content as HSO's programs evolve
- Monitoring API costs
- Updating the model selection if better/cheaper options emerge

See [docs/for-developers/maintenance.md](docs/for-developers/maintenance.md).
