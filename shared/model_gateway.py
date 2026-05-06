"""
Model gateway — provider-agnostic interface to LLMs.

This is the ONLY place in the codebase that talks to a model API directly.
All agents call into this module, which routes to OpenRouter (or any other
provider) without the agent caring which one.

Why this matters:
    HSO's system must not lock into a single model provider. By keeping all
    model calls behind this interface, switching from Claude to GPT to Gemini
    to a self-hosted Llama is a config change, not a code change.

Usage:
    from shared.model_gateway import call_model

    response = call_model(
        model="claude-sonnet",       # logical name, mapped to provider
        system_prompt="You are...",
        user_message="Hello",
        max_tokens=500,
        temperature=0.3,
    )
    print(response.content)
    print(response.tokens_used)

Adding a new provider: implement a Provider subclass below and register it
in PROVIDERS. No changes anywhere else in the codebase.
"""

from __future__ import annotations

import json
import logging
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

import requests

logger = logging.getLogger(__name__)


# ============================================================================
# Public types
# ============================================================================

@dataclass
class ModelResponse:
    """Standardized response from any provider."""
    content: str
    tokens_used: int
    model_used: str  # the actual model name the provider used
    provider: str    # which provider served the request
    latency_ms: int
    finish_reason: str = ""  # stop, length, etc.


@dataclass
class ModelError(Exception):
    """Raised when a model call fails after retries."""
    message: str
    provider: str
    last_status_code: Optional[int] = None

    def __str__(self) -> str:
        return f"[{self.provider}] {self.message}"


# ============================================================================
# Logical model names → provider/model mapping
#
# Agents reference logical names like "drafter" or "classifier". This indirection
# means agents are unaware of which underlying model is being used. Set the
# environment variables to swap models without code changes.
# ============================================================================

LOGICAL_MODELS = {
    "classifier": os.environ.get(
        "HSO_MODEL_CLASSIFIER", "openrouter:anthropic/claude-haiku-4.5"
    ),
    "drafter": os.environ.get(
        "HSO_MODEL_DRAFTER", "openrouter:anthropic/claude-sonnet-4.6"
    ),
    "researcher": os.environ.get(
        "HSO_MODEL_RESEARCHER", "openrouter:anthropic/claude-sonnet-4.6"
    ),
    "writer": os.environ.get(
        "HSO_MODEL_WRITER", "openrouter:anthropic/claude-opus-4.7"
    ),
}


def resolve_model(logical_or_concrete: str) -> tuple[str, str]:
    """
    Take a logical name ("drafter") or a concrete spec ("openrouter:openai/gpt-4o")
    and return (provider, model_id).
    """
    spec = LOGICAL_MODELS.get(logical_or_concrete, logical_or_concrete)
    if ":" not in spec:
        # Default to openrouter if no provider prefix
        provider = "openrouter"
        model_id = spec
    else:
        provider, model_id = spec.split(":", 1)
    return provider, model_id


# ============================================================================
# Provider interface
# ============================================================================

class Provider(ABC):
    """All providers implement this interface."""

    name: str = "abstract"

    @abstractmethod
    def call(
        self,
        model_id: str,
        system_prompt: str,
        user_message: str,
        max_tokens: int,
        temperature: float,
    ) -> ModelResponse:
        ...

    @abstractmethod
    def is_configured(self) -> bool:
        """Return True if this provider has the credentials it needs."""
        ...


# ============================================================================
# OpenRouter provider — the recommended default
# ============================================================================

class OpenRouterProvider(Provider):
    """
    OpenRouter gives access to Claude, GPT, Gemini, Llama, and dozens of
    other models through one OpenAI-compatible API.

    https://openrouter.ai/
    """

    name = "openrouter"

    def __init__(self) -> None:
        self.api_key = os.environ.get("OPENROUTER_API_KEY", "")
        self.endpoint = "https://openrouter.ai/api/v1/chat/completions"
        # OpenRouter asks callers to identify themselves; nice to be polite.
        self.referer = os.environ.get("HSO_APP_URL", "https://hopespot.no")
        self.app_title = "HSO Agent System"

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def call(
        self,
        model_id: str,
        system_prompt: str,
        user_message: str,
        max_tokens: int,
        temperature: float,
    ) -> ModelResponse:
        if not self.is_configured():
            raise ModelError(
                "OPENROUTER_API_KEY not set. Get one at https://openrouter.ai/",
                provider=self.name,
            )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": self.referer,
            "X-Title": self.app_title,
        }
        payload = {
            "model": model_id,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        last_error = None
        last_status = None
        started = time.time()

        # Two retries with exponential backoff for transient failures.
        for attempt in range(3):
            try:
                r = requests.post(
                    self.endpoint, headers=headers, json=payload, timeout=60
                )
                last_status = r.status_code
                r.raise_for_status()
                data = r.json()

                latency_ms = int((time.time() - started) * 1000)
                choice = data["choices"][0]
                content = choice["message"]["content"]
                finish_reason = choice.get("finish_reason", "")
                tokens = data.get("usage", {}).get("total_tokens", 0)

                return ModelResponse(
                    content=content,
                    tokens_used=tokens,
                    model_used=data.get("model", model_id),
                    provider=self.name,
                    latency_ms=latency_ms,
                    finish_reason=finish_reason,
                )
            except requests.RequestException as e:
                last_error = e
                logger.warning(
                    "OpenRouter call failed attempt=%d status=%s err=%s",
                    attempt + 1, last_status, e,
                )
                if attempt < 2:
                    time.sleep(2 ** attempt)

        raise ModelError(
            f"OpenRouter call failed after retries: {last_error}",
            provider=self.name,
            last_status_code=last_status,
        )


# ============================================================================
# Anthropic provider — direct, for organizations preferring native API
# ============================================================================

class AnthropicProvider(Provider):
    """Direct Anthropic API. Use only if there's a specific reason not to use OpenRouter."""

    name = "anthropic"

    def __init__(self) -> None:
        self.api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        self.endpoint = "https://api.anthropic.com/v1/messages"
        self.api_version = "2023-06-01"

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def call(
        self,
        model_id: str,
        system_prompt: str,
        user_message: str,
        max_tokens: int,
        temperature: float,
    ) -> ModelResponse:
        if not self.is_configured():
            raise ModelError(
                "ANTHROPIC_API_KEY not set",
                provider=self.name,
            )

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": self.api_version,
            "Content-Type": "application/json",
        }
        # Anthropic's API takes system as a top-level field.
        payload = {
            "model": model_id,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": system_prompt,
            "messages": [
                {"role": "user", "content": user_message},
            ],
        }

        last_error = None
        last_status = None
        started = time.time()

        for attempt in range(3):
            try:
                r = requests.post(
                    self.endpoint, headers=headers, json=payload, timeout=60
                )
                last_status = r.status_code
                r.raise_for_status()
                data = r.json()

                latency_ms = int((time.time() - started) * 1000)
                # Anthropic returns content as a list of blocks; we only handle text.
                blocks = data.get("content", [])
                content = "".join(
                    b.get("text", "") for b in blocks if b.get("type") == "text"
                )
                tokens = (
                    data.get("usage", {}).get("input_tokens", 0)
                    + data.get("usage", {}).get("output_tokens", 0)
                )
                return ModelResponse(
                    content=content,
                    tokens_used=tokens,
                    model_used=data.get("model", model_id),
                    provider=self.name,
                    latency_ms=latency_ms,
                    finish_reason=data.get("stop_reason", ""),
                )
            except requests.RequestException as e:
                last_error = e
                logger.warning(
                    "Anthropic call failed attempt=%d status=%s err=%s",
                    attempt + 1, last_status, e,
                )
                if attempt < 2:
                    time.sleep(2 ** attempt)

        raise ModelError(
            f"Anthropic call failed after retries: {last_error}",
            provider=self.name,
            last_status_code=last_status,
        )


# ============================================================================
# OpenAI provider — direct, for organizations preferring native API
# ============================================================================

class OpenAIProvider(Provider):
    """Direct OpenAI API."""

    name = "openai"

    def __init__(self) -> None:
        self.api_key = os.environ.get("OPENAI_API_KEY", "")
        self.endpoint = "https://api.openai.com/v1/chat/completions"

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def call(
        self,
        model_id: str,
        system_prompt: str,
        user_message: str,
        max_tokens: int,
        temperature: float,
    ) -> ModelResponse:
        if not self.is_configured():
            raise ModelError("OPENAI_API_KEY not set", provider=self.name)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model_id,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        last_error = None
        last_status = None
        started = time.time()

        for attempt in range(3):
            try:
                r = requests.post(
                    self.endpoint, headers=headers, json=payload, timeout=60
                )
                last_status = r.status_code
                r.raise_for_status()
                data = r.json()

                latency_ms = int((time.time() - started) * 1000)
                choice = data["choices"][0]
                return ModelResponse(
                    content=choice["message"]["content"],
                    tokens_used=data.get("usage", {}).get("total_tokens", 0),
                    model_used=data.get("model", model_id),
                    provider=self.name,
                    latency_ms=latency_ms,
                    finish_reason=choice.get("finish_reason", ""),
                )
            except requests.RequestException as e:
                last_error = e
                logger.warning(
                    "OpenAI call failed attempt=%d status=%s err=%s",
                    attempt + 1, last_status, e,
                )
                if attempt < 2:
                    time.sleep(2 ** attempt)

        raise ModelError(
            f"OpenAI call failed after retries: {last_error}",
            provider=self.name,
            last_status_code=last_status,
        )


# ============================================================================
# Mock provider — for offline tests and CI
# ============================================================================

class MockProvider(Provider):
    """Returns canned responses based on input keywords. Used in tests."""

    name = "mock"

    def __init__(self, response_map: Optional[dict] = None) -> None:
        self.response_map = response_map or {}

    def is_configured(self) -> bool:
        return True

    def call(
        self,
        model_id: str,
        system_prompt: str,
        user_message: str,
        max_tokens: int,
        temperature: float,
    ) -> ModelResponse:
        # Look for matching keys in response_map; otherwise return generic.
        for trigger, response in self.response_map.items():
            if trigger.lower() in user_message.lower():
                return ModelResponse(
                    content=response,
                    tokens_used=100,
                    model_used=model_id,
                    provider=self.name,
                    latency_ms=10,
                )
        return ModelResponse(
            content="[mock response]",
            tokens_used=100,
            model_used=model_id,
            provider=self.name,
            latency_ms=10,
        )


# ============================================================================
# Provider registry & main entry point
# ============================================================================

PROVIDERS: dict[str, Provider] = {}


def get_provider(name: str) -> Provider:
    """Lazy-instantiate providers so we don't fail on missing creds for unused providers."""
    if name not in PROVIDERS:
        if name == "openrouter":
            PROVIDERS[name] = OpenRouterProvider()
        elif name == "anthropic":
            PROVIDERS[name] = AnthropicProvider()
        elif name == "openai":
            PROVIDERS[name] = OpenAIProvider()
        elif name == "mock":
            PROVIDERS[name] = MockProvider()
        else:
            raise ValueError(f"Unknown provider: {name}")
    return PROVIDERS[name]


def set_provider(name: str, provider: Provider) -> None:
    """Override a provider — used in tests to inject a MockProvider."""
    PROVIDERS[name] = provider


def call_model(
    model: str,
    system_prompt: str,
    user_message: str,
    max_tokens: int = 1000,
    temperature: float = 0.3,
) -> ModelResponse:
    """
    Main entry point.

    `model` can be:
      - A logical name registered in LOGICAL_MODELS (e.g. "drafter")
      - A concrete spec like "openrouter:anthropic/claude-haiku-4.5"
      - A bare model ID, defaulting to OpenRouter
    """
    provider_name, model_id = resolve_model(model)
    provider = get_provider(provider_name)
    return provider.call(
        model_id=model_id,
        system_prompt=system_prompt,
        user_message=user_message,
        max_tokens=max_tokens,
        temperature=temperature,
    )


# ============================================================================
# Cost estimation — for logging only, NOT authoritative billing
# ============================================================================

# Cost per 1M total tokens (input+output blended estimate). Update as prices change.
APPROX_COST_PER_MILLION_USD = {
    # Anthropic via OpenRouter or direct
    "claude-haiku-4.5": 1.0,
    "claude-sonnet-4.6": 3.0,
    "claude-opus-4.7": 15.0,
    # OpenAI
    "gpt-4o-mini": 0.20,
    "gpt-4o": 3.0,
    # Google
    "gemini-flash-1.5": 0.10,
    "gemini-pro-1.5": 2.0,
    # Open source
    "llama-3.1-70b-instruct": 0.50,
    "mistral-large": 3.0,
}


def estimate_cost_usd(model_id: str, tokens: int) -> float:
    """Best-effort cost estimate. Falls back to a mid-range default."""
    # Match on the model name's last segment (handles "anthropic/claude-haiku-4.5")
    short = model_id.split("/")[-1].lower()
    for key, rate in APPROX_COST_PER_MILLION_USD.items():
        if key in short:
            return (tokens / 1_000_000) * rate
    # Default to mid-range pricing if we don't recognize the model.
    return (tokens / 1_000_000) * 2.0
