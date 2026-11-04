"""Model providers. Address a model as ``provider:model``, e.g. ``anthropic:claude-opus-5-5``,
``openai:gpt-5``, ``xai:grok-4``, ``gemini:gemini-2.5-pro``, ``openrouter:qwen/qwen3-coder``,
``ollama:qwen2.5-coder:32b``."""

from __future__ import annotations

import importlib.util
import os

from .base import Conversation, Provider, ProviderError, ToolCall, ToolResult, ToolSpec, Turn, Usage
from .openai_compat import ENDPOINTS

__all__ = [
    "Conversation",
    "Provider",
    "ProviderError",
    "ToolCall",
    "ToolResult",
    "ToolSpec",
    "Turn",
    "Usage",
    "create",
    "describe_providers",
    "parse_ref",
]


def parse_ref(ref: str) -> tuple[str, str]:
    if ":" not in ref:
        raise ProviderError(f"Model '{ref}' must be written as provider:model, e.g. anthropic:claude-opus-5-5")
    provider, model = ref.split(":", 1)
    return provider.strip().lower(), model.strip()


def create(ref: str, effort: str | None = "high") -> Provider:
    provider, model = parse_ref(ref)
    if provider in ("anthropic", "claude"):
        from .anthropic import AnthropicProvider

        return AnthropicProvider(model, effort=effort)
    if provider in ("gemini", "google"):
        from .gemini import GeminiProvider

        return GeminiProvider(model, effort=effort)
    if provider == "scripted":
        from .scripted import ScriptedProvider

        return ScriptedProvider(model)
    if provider in ENDPOINTS:
        from .openai_compat import OpenAICompatProvider

        return OpenAICompatProvider(provider, model, effort=effort)
    known = ", ".join(["anthropic", "gemini", *ENDPOINTS])
    raise ProviderError(f"Unknown provider '{provider}'. Known providers: {known}")


def describe_providers() -> list[dict[str, str]]:
    def sdk(mod: str) -> bool:
        try:
            return importlib.util.find_spec(mod) is not None
        except ModuleNotFoundError:
            return False

    rows = [
        {
            "provider": "anthropic",
            "example": "anthropic:claude-opus-5-5",
            "sdk": "yes" if sdk("anthropic") else "pip install 'openfix[anthropic]'",
            "credentials": "ANTHROPIC_API_KEY" + (" (set)" if os.environ.get("ANTHROPIC_API_KEY") else ""),
        },
        {
            "provider": "gemini",
            "example": "gemini:gemini-2.5-pro",
            "sdk": "yes" if sdk("google.genai") else "pip install 'openfix[gemini]'",
            "credentials": "GEMINI_API_KEY" + (" (set)" if os.environ.get("GEMINI_API_KEY") else ""),
        },
    ]
    examples = {
        "openai": "openai:gpt-5",
        "xai": "xai:grok-4",
        "openrouter": "openrouter:qwen/qwen3-coder",
        "groq": "groq:moonshotai/kimi-k2-instruct",
        "deepseek": "deepseek:deepseek-chat",
        "mistral": "mistral:devstral-medium-latest",
        "together": "together:Qwen/Qwen3-Coder-480B-A35B-Instruct-FP8",
        "fireworks": "fireworks:accounts/fireworks/models/qwen3-coder-480b-a35b-instruct",
        "ollama": "ollama:qwen2.5-coder:32b",
        "vllm": "vllm:<served-model-name>",
        "lmstudio": "lmstudio:<model>",
        "compat": "compat:<model> (OPENFIX_COMPAT_BASE_URL)",
    }
    for name, ep in ENDPOINTS.items():
        cred = "none (local)" if ep.local else (ep.key_env or "")
        if ep.key_env and os.environ.get(ep.key_env):
            cred += " (set)"
        rows.append(
            {
                "provider": name,
                "example": examples.get(name, f"{name}:<model>"),
                "sdk": "yes" if sdk("openai") else "pip install 'openfix[openai]'",
                "credentials": cred,
            }
        )
    return rows
