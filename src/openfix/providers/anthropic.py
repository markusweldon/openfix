"""Claude via the official Anthropic SDK (Messages API, manual tool loop)."""

from __future__ import annotations

import os
import re
from typing import Any

from .base import Conversation, ProviderError, StopReason, ToolCall, ToolResult, ToolSpec, Turn, Usage, require_module

# Models that take adaptive thinking + output_config.effort.
_MODERN = re.compile(r"claude-(fable|mythos|opus-[45]-[5-9]|opus-5|sonnet-[45]-[5-9]|sonnet-5|haiku-5)")
# Models that accept the server-side refusal fallback (`fallbacks: "default"`).
_FALLBACK = re.compile(r"^claude-(fable-5-1|opus-5-5|opus-5|sonnet-5-5)$")


class AnthropicProvider:
    name = "anthropic"
    local = False

    def __init__(self, model: str, effort: str | None = "high", max_tokens: int = 32000) -> None:
        self.model = model
        self.effort = effort
        self.max_tokens = max_tokens
        sdk = require_module("anthropic", "anthropic")
        self._sdk = sdk
        self._client = sdk.Anthropic(max_retries=4)

    def start(self, system: str, tools: list[ToolSpec]) -> Conversation:
        return _AnthropicConversation(self, system, tools)


class _AnthropicConversation:
    def __init__(self, provider: AnthropicProvider, system: str, tools: list[ToolSpec]) -> None:
        self.p = provider
        self.system = system
        self.tools = [{"name": t.name, "description": t.description, "input_schema": t.parameters} for t in tools]
        self.messages: list[dict[str, Any]] = []

    def _params(self) -> dict[str, Any]:
        params: dict[str, Any] = {
            "model": self.p.model,
            "max_tokens": self.p.max_tokens,
            # Stable prefix (tools + system) is cached across turns.
            "system": [{"type": "text", "text": self.system, "cache_control": {"type": "ephemeral"}}],
            "messages": self.messages,
        }
        if self.tools:
            params["tools"] = self.tools
        if _MODERN.search(self.p.model):
            params["thinking"] = {"type": "adaptive"}
            if self.p.effort:
                params["output_config"] = {"effort": self.p.effort}
        extra_headers: dict[str, str] = {}
        extra_body: dict[str, Any] = {}
        if _FALLBACK.match(self.p.model) and os.environ.get("OPENFIX_ANTHROPIC_FALLBACKS", "1") != "0":
            # On a safety-classifier decline, the API re-runs the request on a suitable model.
            extra_headers["anthropic-beta"] = "server-side-fallback-2026-07-01"
            extra_body["fallbacks"] = "default"
        if extra_headers:
            params["extra_headers"] = extra_headers
        if extra_body:
            params["extra_body"] = extra_body
        return params

    def send(self, *, user: str | None = None, tool_results: list[ToolResult] | None = None) -> Turn:
        content: list[dict[str, Any]] = []
        for r in tool_results or []:
            content.append(
                {"type": "tool_result", "tool_use_id": r.call_id, "content": r.content, "is_error": r.is_error}
            )
        if user:
            content.append({"type": "text", "text": user})
        if not content:
            raise ProviderError("Nothing to send")
        self.messages.append({"role": "user", "content": content})

        sdk = self.p._sdk
        while True:
            try:
                with self.p._client.messages.stream(**self._params()) as stream:
                    response = stream.get_final_message()
            except sdk.APIStatusError as exc:
                raise ProviderError(f"Anthropic API error {exc.status_code}: {exc.message}") from exc
            except sdk.APIConnectionError as exc:
                raise ProviderError(f"Could not reach the Anthropic API: {exc}") from exc
            # Replay the assistant turn unchanged (thinking blocks included).
            self.messages.append({"role": "assistant", "content": response.content})
            if response.stop_reason == "pause_turn":
                continue
            break

        text = "".join(b.text for b in response.content if getattr(b, "type", "") == "text")
        calls = [
            ToolCall(id=b.id, name=b.name, arguments=dict(b.input or {}))
            for b in response.content
            if getattr(b, "type", "") == "tool_use"
        ]
        u = response.usage
        usage = Usage(
            input_tokens=(u.input_tokens or 0) + (getattr(u, "cache_creation_input_tokens", 0) or 0),
            output_tokens=u.output_tokens or 0,
            cache_read_tokens=getattr(u, "cache_read_input_tokens", 0) or 0,
        )
        stop: StopReason = {
            "tool_use": "tool_use",
            "end_turn": "end",
            "stop_sequence": "end",
            "max_tokens": "max_tokens",
            "refusal": "refusal",
        }.get(response.stop_reason or "", "end")  # type: ignore[assignment]
        if calls:
            stop = "tool_use"
        return Turn(text=text, tool_calls=calls, stop=stop, usage=usage, model=getattr(response, "model", None))
