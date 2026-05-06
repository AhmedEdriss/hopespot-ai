# Model Portability

This document explains how this system is designed to work across LLM providers — and what to know when swapping models in practice.

## The principle

**No provider lock-in.** The system must be able to swap from Claude to GPT to Gemini to a self-hosted model without rewriting the agents.

This is a non-negotiable design constraint, not a "nice to have." Reasons:

1. **Pricing changes.** Provider pricing shifts unpredictably. Being stuck with one provider when costs spike is bad.
2. **Capability changes.** New models from different providers leapfrog each other constantly. We want to use whatever's best for HSO's tasks at any given time.
3. **Reliability.** Provider outages happen. Fallbacks save the day.
4. **HSO's autonomy.** HSO should not be tied to any single AI vendor's strategic choices.

## How the architecture enforces this

### One model gateway, all calls go through it

`shared/model_gateway.py` is the only file in this codebase that talks to a model API directly. Every agent calls `call_model()` from this module. The gateway:

- Resolves logical model names (`"drafter"`) to concrete provider+model
- Handles provider-specific request/response formats
- Returns a standardized `ModelResponse` that hides provider differences
- Implements retries and error handling consistently

If you find yourself reaching for `requests.post("https://api.anthropic.com/...")` or `import anthropic` anywhere outside the gateway, you're breaking the abstraction. Stop and add it to the gateway instead.

### Logical model names, not concrete model IDs

Agent code references models by their **role**, not their identity:

```python
# Good — agent code
response = call_model(model="drafter", ...)

# Bad — agent code (locks the agent to a specific model)
response = call_model(model="anthropic/claude-sonnet-4.6", ...)
```

The mapping from logical names to concrete models lives in `shared/model_gateway.LOGICAL_MODELS`, configurable via environment variables:

```bash
HSO_MODEL_CLASSIFIER=openrouter:anthropic/claude-haiku-4.5
HSO_MODEL_DRAFTER=openrouter:anthropic/claude-sonnet-4.6
HSO_MODEL_RESEARCHER=openrouter:anthropic/claude-sonnet-4.6
HSO_MODEL_WRITER=openrouter:anthropic/claude-opus-4.7
```

To swap any of these, change the env var. No code change.

### Prompts written for portability

Prompts in this codebase follow these rules:

1. **Explicit, structured instructions.** Don't rely on a model's defaults — say what you want.
2. **Worked examples.** Few-shot prompting grounds all models toward consistent behavior.
3. **No provider-specific features in core prompts.** No XML tags assumed (Claude convention), no schema-mode syntax (OpenAI), no Gemini multi-turn tricks. Plain text instructions and JSON output.
4. **Output format is regex-parseable.** Whether it's JSON or a special marker like `[ESCALATE: ...]`, the parser works regardless of which model produced the output.

## What "portable" actually means

It's worth being honest: **portable does not mean identical**.

Different models genuinely behave differently:

- Claude tends toward more cautious, hedged phrasing
- GPT tends toward more concise, confident output
- Gemini tends toward more literal interpretation
- Open-source models vary widely

Even with identical prompts, you'll get noticeably different drafts.

The goal is **swap-able with predictable adjustment**, not **swap with zero difference**:

- The architecture supports the swap without code changes
- Prompts may need light retuning per model for best results
- Quality monitoring (see `metrics.md` per agent) will surface where adjustment is needed

## Recommended providers

### Default: OpenRouter

OpenRouter (https://openrouter.ai/) gives access to Claude, GPT, Gemini, Llama, Mistral, and dozens of other models through one OpenAI-compatible API. We default to it because:

- Single API key, many models
- Switch models via configuration
- Built-in fallback support
- Pricing is roughly pass-through with a small markup
- Reasonable for nonprofits

### Direct provider APIs

Sometimes you want to talk to a provider directly:

- Anthropic (`shared/model_gateway.AnthropicProvider`)
- OpenAI (`shared/model_gateway.OpenAIProvider`)

Set the appropriate API keys (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`) and use the `anthropic:` or `openai:` prefix in your model env var. Useful when:

- A provider releases a feature OpenRouter hasn't picked up yet
- You want to avoid the OpenRouter markup at very high volume
- You want a direct billing relationship with the provider

### Self-hosted models

For organizations that want to run models on their own hardware:

1. Use a server like vLLM, Ollama, or LM Studio that exposes an OpenAI-compatible endpoint
2. Add a custom provider class in `shared/model_gateway.py` that points at your endpoint
3. Reference it in `LOGICAL_MODELS` like `"selfhosted:llama-3.1-70b"`

This is the path for full data sovereignty (no data leaves HSO's infrastructure). Tradeoff: you manage the infrastructure.

## Switching models in practice

The full process:

1. **Pick a target model.** Look at OpenRouter's model list, recent benchmarks, and HSO's task profile.
2. **Test it on the test suite.** `HSO_MODEL_DRAFTER=newmodel python tests/test_email_pipeline.py` — confirms structural compatibility (the test mock doesn't run the real model, but the agent code path is exercised).
3. **Test it on real samples.** Run `agents/email/run_cli.py --folder tests/sample_emails/` with both the old and new model and compare outputs by hand.
4. **Soft launch.** Deploy with the new model in a staging environment. Have HSO leadership review a handful of drafts.
5. **Roll forward.** If quality holds, change the production env var. If not, revert is one variable away.

## Testing across providers

The CI pipeline (`.github/workflows/ci.yml`) runs the offline tests with mocked providers. To validate against real providers, run:

```bash
# Test against Claude
HSO_MODEL_CLASSIFIER=openrouter:anthropic/claude-haiku-4.5 \
HSO_MODEL_DRAFTER=openrouter:anthropic/claude-sonnet-4.6 \
python agents/email/run_cli.py --folder tests/sample_emails/

# Test against GPT
HSO_MODEL_CLASSIFIER=openrouter:openai/gpt-4o-mini \
HSO_MODEL_DRAFTER=openrouter:openai/gpt-4o \
python agents/email/run_cli.py --folder tests/sample_emails/

# Test against Gemini
HSO_MODEL_CLASSIFIER=openrouter:google/gemini-flash-1.5 \
HSO_MODEL_DRAFTER=openrouter:google/gemini-pro-1.5 \
python agents/email/run_cli.py --folder tests/sample_emails/
```

Cost: under $1 per full run.

A quarterly cross-provider test is a good practice — it catches drift, surfaces emerging better options, and keeps the portability promise honest.

## What about provider-specific features?

Some features are genuinely provider-specific and worth using:

- **Anthropic prompt caching** — can reduce costs ~80% for repeated context. Useful when stable.
- **OpenAI structured outputs** — guaranteed JSON adherence. Useful for the classifier.
- **Gemini long context** — 2M+ tokens for cases that need it.

Rules for using provider-specific features:

1. **Add them in the gateway, not the agent.** Provider differences belong in `model_gateway.py`.
2. **Make them optional.** The agent must work whether the optimization is on or off.
3. **Document the feature.** Note in `model-portability.md` that "if you swap to provider X, you lose feature Y."
4. **Don't depend on any single provider's feature for correctness.** Use them for cost/latency optimization only.

## Exit plan summary

If HSO ever needs to fully migrate off a specific provider:

1. Set the env vars to point at the new provider
2. Run the test suite
3. Run a real-sample comparison
4. Deploy

That's it. The codebase is structured so this is a 30-minute task, not a multi-week migration.

The cost of this design (slight extra abstraction, occasional slight underuse of provider-specific features) is small. The benefit (resilience, optionality, no lock-in) compounds over time.
