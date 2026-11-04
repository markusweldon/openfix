"""Google Gemini via the official google-genai SDK (Gemini API or Vertex AI)."""

from __future__ import annotations

import uuid
from typing import Any

from .base import Conversation, ProviderError, ToolCall, ToolResult, ToolSpec, Turn, Usage, require_module


class GeminiProvider:
    name = "gemini"
    local = False

    def __init__(self, model: str, effort: str | None = "high") -> None:
        self.model = model
        self.effort = effort
        genai = require_module("google.genai", "gemini")
        self._types = require_module("google.genai.types", "gemini")
        try:
            self._client = genai.Client()  # GEMINI_API_KEY / GOOGLE_API_KEY, or Vertex via GOOGLE_GENAI_USE_VERTEXAI
        except Exception as exc:  # noqa: BLE001 - SDK raises plain ValueError without credentials
            raise ProviderError(f"Gemini client could not start: {exc}") from exc

    def start(self, system: str, tools: list[ToolSpec]) -> Conversation:
        return _GeminiConversation(self, system, tools)


class _GeminiConversation:
    def __init__(self, p: GeminiProvider, system: str, tools: list[ToolSpec]) -> None:
        self.p = p
        t = p._types
        decls = [
            t.FunctionDeclaration(name=s.name, description=s.description, parameters_json_schema=s.parameters)
            for s in tools
        ]
        config = t.GenerateContentConfig(
            system_instruction=system,
            tools=[t.Tool(function_declarations=decls)] if decls else None,
            automatic_function_calling=t.AutomaticFunctionCallingConfig(disable=True),
        )
        self.chat = p._client.chats.create(model=p.model, config=config)

    def send(self, *, user: str | None = None, tool_results: list[ToolResult] | None = None) -> Turn:
        t = self.p._types
        parts: list[Any] = [
            t.Part.from_function_response(
                name=r.name, response={"error": r.content} if r.is_error else {"result": r.content}
            )
            for r in tool_results or []
        ]
        if user:
            parts.append(t.Part.from_text(text=user))
        try:
            resp = self.chat.send_message(parts)
        except Exception as exc:  # noqa: BLE001 - google-genai error types vary by transport
            raise ProviderError(f"Gemini API error: {exc}") from exc
        calls = [
            ToolCall(id=fc.id or f"call_{uuid.uuid4().hex[:8]}", name=fc.name, arguments=dict(fc.args or {}))
            for fc in resp.function_calls or []
        ]
        meta = resp.usage_metadata
        usage = Usage(
            input_tokens=getattr(meta, "prompt_token_count", 0) or 0,
            output_tokens=(getattr(meta, "candidates_token_count", 0) or 0)
            + (getattr(meta, "thoughts_token_count", 0) or 0),
            cache_read_tokens=getattr(meta, "cached_content_token_count", 0) or 0,
        )
        finish = ""
        if resp.candidates:
            finish = str(getattr(resp.candidates[0], "finish_reason", "") or "")
        stop = (
            "tool_use"
            if calls
            else ("max_tokens" if "MAX_TOKENS" in finish else "refusal" if "SAFETY" in finish else "end")
        )
        text = ""
        try:
            text = resp.text or ""
        except (ValueError, AttributeError):
            text = ""
        return Turn(text=text, tool_calls=calls, stop=stop, usage=usage, model=self.p.model)  # type: ignore[arg-type]
