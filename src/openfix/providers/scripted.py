"""A deterministic provider for tests and offline demos.

It replays a script of tool calls (a JSON/YAML list) instead of calling a model:

    - tool: edit_file
      args: {path: src/files.js, old_text: "...", new_text: "..."}
    - tool: submit
      args: {summary: "..."}
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from .base import Conversation, ProviderError, ToolCall, ToolResult, ToolSpec, Turn, Usage


class ScriptedProvider:
    name = "scripted"
    local = True

    def __init__(self, model: str, steps: list[dict[str, Any]] | None = None) -> None:
        self.model = model
        if steps is None:
            cwd = Path.cwd().resolve()
            path = (cwd / model).resolve()
            if cwd not in path.parents or path.suffix not in (".yaml", ".yml", ".json") or not path.is_file():
                raise ProviderError(
                    "scripted provider needs a .yaml/.json script inside the current directory: "
                    "--model scripted:path/to/script.yaml"
                )
            steps = yaml.safe_load(path.read_text(encoding="utf-8")) or []
        self.steps = steps
        self.transcript: list[dict[str, Any]] = []

    def start(self, system: str, tools: list[ToolSpec]) -> Conversation:
        return _ScriptedConversation(self, system)


class _ScriptedConversation:
    def __init__(self, p: ScriptedProvider, system: str) -> None:
        self.p = p
        self.i = 0
        p.transcript.append({"system": system})

    def send(self, *, user: str | None = None, tool_results: list[ToolResult] | None = None) -> Turn:
        self.p.transcript.append({"user": user, "tool_results": [r.__dict__ for r in tool_results or []]})
        if self.i >= len(self.p.steps):
            return Turn(text="(script finished)", tool_calls=[], stop="end", usage=Usage(10, 5))
        step = self.p.steps[self.i]
        self.i += 1
        if "text" in step and "tool" not in step:
            return Turn(text=str(step["text"]), tool_calls=[], stop="end", usage=Usage(10, 5))
        call = ToolCall(id=f"call_{self.i}", name=step["tool"], arguments=dict(step.get("args") or {}))
        return Turn(text=step.get("say", ""), tool_calls=[call], stop="tool_use", usage=Usage(100, 50))

    def __repr__(self) -> str:  # pragma: no cover
        return json.dumps(self.p.steps)[:80]
