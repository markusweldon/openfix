"""Cost accounting. Token counts are always recorded; dollar amounts only when a price is known.

Add or override prices in the policy file::

    pricing:
      openai:gpt-5: [1.25, 10.0]     # USD per million input, output tokens
"""

from __future__ import annotations

from .providers.base import Usage

# USD per million tokens (input, output). Anthropic first-party list prices.
BUILTIN: dict[str, tuple[float, float]] = {
    "anthropic:claude-fable-5-1": (10.0, 50.0),
    "anthropic:claude-opus-5-5": (4.0, 20.0),
    "anthropic:claude-opus-5": (5.0, 25.0),
    "anthropic:claude-opus-4-8": (5.0, 25.0),
    "anthropic:claude-sonnet-5-5": (2.0, 10.0),
    "anthropic:claude-sonnet-5": (2.0, 10.0),
    "anthropic:claude-sonnet-4-6": (3.0, 15.0),
    "anthropic:claude-haiku-5-5": (0.10, 0.50),
    "anthropic:claude-haiku-4-5": (1.0, 5.0),
}

LOCAL = {"ollama", "vllm", "lmstudio", "scripted"}


def cost_usd(
    provider: str, model: str, usage: Usage, extra: dict[str, tuple[float, float]] | None = None
) -> float | None:
    if provider in LOCAL:
        return 0.0
    key = f"{provider}:{model}"
    price = (extra or {}).get(key) or BUILTIN.get(key)
    if not price:
        return None
    pin, pout = price
    # Cache reads are billed at roughly a tenth of the input price on most providers.
    return round((usage.input_tokens * pin + usage.cache_read_tokens * pin * 0.1 + usage.output_tokens * pout) / 1e6, 4)
