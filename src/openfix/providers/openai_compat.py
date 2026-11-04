"""Any OpenAI-compatible Chat Completions endpoint: OpenAI, xAI Grok, OpenRouter, Groq, DeepSeek,
Mistral, Together, Fireworks, Azure-style gateways, and local servers (Ollama, vLLM, LM Studio, llama.cpp)."""

from __future__ import annotations

import json
import os
import secrets
from dataclasses import dataclass
from typing import Any

from .base import Conversation, ProviderError, ToolCall, ToolResult, ToolSpec, Turn, Usage, require_module


@dataclass(frozen=True)
class Endpoint:
    base_url: str | None
    key_env: str | None
    local: bool = False
    reasoning_effort: bool = False  # accepts the `reasoning_effort` parameter


ENDPOINTS: dict[str, Endpoint] = {
    "openai": Endpoint(None, "OPENAI_API_KEY", reasoning_effort=True),
    "xai": Endpoint("https://api.x.ai/v1", "XAI_API_KEY"),
    "openrouter": Endpoint("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
    "groq": Endpoint("https://api.groq.com/openai/v1", "GROQ_API_KEY"),
    "deepseek": Endpoint("https://api.deepseek.com/v1", "DEEPSEEK_API_KEY"),
    "mistral": Endpoint("https://api.mistral.ai/v1", "MISTRAL_API_KEY"),
    "together": Endpoint("https://api.together.xyz/v1", "TOGETHER_API_KEY"),
    "fireworks": Endpoint("https://api.fireworks.ai/inference/v1", "FIREWORKS_API_KEY"),
    "ollama": Endpoint("http://localhost:11434/v1", None, local=True),
    "vllm": Endpoint("http://localhost:8000/v1", None, local=True),
    "lmstudio": Endpoint("http://localhost:1234/v1", None, local=True),
    # Generic: set OPENFIX_COMPAT_BASE_URL (and optionally OPENFIX_COMPAT_API_KEY).
    "compat": Endpoint(None, "OPENFIX_COMPAT_API_KEY"),
}

_EFFORT_MAP = {"low": "low", "medium": "medium", "high": "high", "xhigh": "high", "max": "high"}


class OpenAICompatProvider:
    def __init__(self, name: str, model: str, effort: str | None = "high") -> None:
        if name not in ENDPOINTS:
            raise ProviderError(f"Unknown OpenAI-compatible provider '{name}'")
        self.name = name
        self.model = model
        self.endpoint = ENDPOINTS[name]
        self.effort = effort
        env_prefix = f"OPENFIX_{name.upper()}"
        base_url = os.environ.get(f"{env_prefix}_BASE_URL") or self.endpoint.base_url
        if name == "compat":
            base_url = os.environ.get("OPENFIX_COMPAT_BASE_URL")
            if not base_url:
                raise ProviderError("Set OPENFIX_COMPAT_BASE_URL for the 'compat' provider")
        self.local = self.endpoint.local or bool(
            base_url and any(h in base_url for h in ("://localhost", "://127.0.0.1", "://[::1]"))
        )
        key = os.environ.get(self.endpoint.key_env) if self.endpoint.key_env else None
        if not key and not self.local:
            raise ProviderError(f"Set {self.endpoint.key_env} to use the '{name}' provider")
        sdk = require_module("openai", "openai")
        self._sdk = sdk
        # Local servers ignore the key, but the SDK requires one: use a random throwaway value.
        api_key = key or secrets.token_urlsafe(16)
        self._client = sdk.OpenAI(api_key=api_key, base_url=base_url, max_retries=4, timeout=600)

    def start(self, system: str, tools: list[ToolSpec]) -> Conversation:
        return _CompatConversation(self, system, tools)


class _CompatConversation:
    def __init__(self, p: OpenAICompatProvider, system: str, tools: list[ToolSpec]) -> None:
        self.p = p
        self.tools = [
            {"type": "function", "function": {"name": t.name, "description": t.description, "parameters": t.parameters}}
            for t in tools
        ]
        self.messages: list[dict[str, Any]] = [{"role": "system", "content": system}]

    def send(self, *, user: str | None = None, tool_results: list[ToolResult] | None = None) -> Turn:
        for r in tool_results or []:
            content = ("ERROR: " if r.is_error else "") + r.content
            self.messages.append({"role": "tool", "tool_call_id": r.call_id, "content": content})
        if user:
            self.messages.append({"role": "user", "content": user})
        params: dict[str, Any] = {"model": self.p.model, "messages": self.messages}
        if self.tools:
            params["tools"] = self.tools
        if self.p.endpoint.reasoning_effort and self.p.effort:
            params["reasoning_effort"] = _EFFORT_MAP.get(self.p.effort, "medium")
        sdk = self.p._sdk
        try:
            resp = self.p._client.chat.completions.create(**params)
        except sdk.BadRequestError as exc:
            if "reasoning_effort" in params and "reasoning" in str(exc).lower():
                params.pop("reasoning_effort")  # model does not support it; retry once without
                resp = self.p._client.chat.completions.create(**params)
            else:
                raise ProviderError(f"{self.p.name} API error: {exc}") from exc
        except sdk.APIStatusError as exc:
            raise ProviderError(f"{self.p.name} API error {exc.status_code}: {exc}") from exc
        except sdk.APIConnectionError as exc:
            raise ProviderError(f"Could not reach {self.p.name}: {exc}") from exc
        if not resp.choices:
            raise ProviderError(f"{self.p.name} returned no choices")
        choice = resp.choices[0]
        msg = choice.message
        assistant: dict[str, Any] = {"role": "assistant", "content": msg.content or ""}
        calls: list[ToolCall] = []
        if msg.tool_calls:
            assistant["tool_calls"] = []
            for tc in msg.tool_calls:
                raw = tc.function.arguments or "{}"
                try:
                    args = json.loads(raw)
                    if not isinstance(args, dict):
                        args = {"_invalid": raw}
                except json.JSONDecodeError:
                    args = {"_invalid": raw}
                calls.append(ToolCall(id=tc.id, name=tc.function.name, arguments=args))
                assistant["tool_calls"].append(
                    {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": raw}}
                )
        self.messages.append(assistant)
        usage = Usage()
        if resp.usage:
            usage.input_tokens = resp.usage.prompt_tokens or 0
            usage.output_tokens = resp.usage.completion_tokens or 0
            details = getattr(resp.usage, "prompt_tokens_details", None)
            usage.cache_read_tokens = getattr(details, "cached_tokens", 0) or 0
        finish = choice.finish_reason or "stop"
        stop = "tool_use" if calls else {"length": "max_tokens", "content_filter": "refusal"}.get(finish, "end")
        return Turn(text=msg.content or "", tool_calls=calls, stop=stop, usage=usage, model=resp.model)  # type: ignore[arg-type]
