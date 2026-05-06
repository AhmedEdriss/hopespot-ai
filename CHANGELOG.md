# Changelog

All notable changes to this project. The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added
- Initial repository structure
- Email agent (Phase 1) with full pipeline: filter → classify → route → draft → self-check
- Provider-agnostic model gateway supporting OpenRouter, Anthropic, OpenAI, and mock providers
- Knowledge base with core docs (voice/tone, about, escalation rules, do-not-say) and starter FAQs
- Make.com blueprint for email agent
- n8n workflow for email agent
- Test suite covering all 10 email categories with 11 sample fixtures
- Deployment configs for Render, Fly.io, and Docker
- HSO-facing documentation (overview, KB update guide)
- Developer documentation (setup, model portability, maintenance, contributing)
- CI workflow

### Pending
- HSO to fill in `[TBD]` items in KB (programs, schedules, escalation contacts)
- First production deployment
- Soft launch with real emails

## How this changelog works

- Entries are written in present tense ("Add", "Fix") in the Added/Changed/Fixed/Removed sections.
- "Unreleased" holds work in progress before a version bump.
- When deploying or shipping a meaningful milestone, move "Unreleased" entries under a new version header with the date.
- Version numbers follow [Semantic Versioning](https://semver.org/) loosely:
  - MAJOR: breaking changes (e.g. new escalation rules that change agent behavior)
  - MINOR: new agents or significant new features
  - PATCH: bug fixes, KB updates, prompt tweaks
