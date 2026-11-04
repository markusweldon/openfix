"""Provider-neutral conversation interface.

Each provider keeps its own native message history (so provider-specific blocks
such as Claude thinking blocks are replayed unchanged) and exposes the same
small surface to the agent loop: send text or tool results, get back text,
tool calls, a stop reason and token usage.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

StopReason = Literal["tool_use", "end", "max_tokens", "refusal", "error"]


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema (object)


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class ToolResult:
    call_id: str
    name: str
    content: str
    is_error: bool = False


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0

    def add(self, other: Usage) -> None:
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.cache_read_tokens += other.cache_read_tokens

    @property
    def total(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class Turn:
    text: str
    tool_calls: list[ToolCall]
    stop: StopReason
    usage: Usage = field(default_factory=Usage)
    model: str | None = None  # the model that actually served the turn (fallbacks may change it)


class Conversation(Protocol):
    def send(self, *, user: str | None = None, tool_results: list[ToolResult] | None = None) -> Turn: ...


class Provider(Protocol):
    name: str
    model: str
    local: bool  # True when inference runs on infrastructure the user controls

    def start(self, system: str, tools: list[ToolSpec]) -> Conversation: ...


class ProviderError(RuntimeError):
    pass


def require_module(module: str, extra: str) -> Any:
    try:
        return __import__(module, fromlist=["_"])
    except ImportError:
        raise ProviderError(
            f"The '{module}' package is not installed. Install it with: pip install 'openfix[{extra}]'"
        ) from None
