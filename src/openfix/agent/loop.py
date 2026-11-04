"""The agent loop: one finding, one model, bounded turns, tokens and cost."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from ..pricing import cost_usd
from ..providers import Provider, ProviderError, ToolResult, Usage
from .prompts import SYSTEM, task_prompt
from .tools import TOOLS, Workspace, render_finding


@dataclass
class AgentRun:
    status: str  # submitted | gave_up | disputed | budget_exhausted | refused | error | no_submission
    turns: int = 0
    usage: Usage = field(default_factory=Usage)
    cost_usd: float | None = None
    models_used: list[str] = field(default_factory=list)
    error: str | None = None
    duration_s: float = 0.0
    final_text: str = ""
    tool_log: list[dict[str, Any]] = field(default_factory=list)


def policy_notes(ws: Workspace) -> str:
    g = ws.policy.guards
    lines = [
        f"- Change at most {g.max_files_changed} files and {g.max_lines_changed} lines in total.",
        f"- Protected paths you cannot modify: {', '.join(g.protected_paths) or 'none'}.",
        "- New dependencies are " + ("allowed if necessary." if g.allow_new_dependencies else "NOT allowed."),
    ]
    if ws.finding.package:
        lines.append(
            "- This is a dependency finding: upgrade to the lowest version that fixes it, keep the "
            "manifest style, and adjust code only if the upgrade requires it."
        )
    return "\n".join(lines)


def run_agent(
    provider: Provider,
    ws: Workspace,
    max_turns: int,
    max_tokens: int,
    max_usd: float | None,
    pricing: dict[str, tuple[float, float]] | None = None,
    on_event: Any = None,
) -> AgentRun:
    start = time.monotonic()
    run = AgentRun(status="no_submission")
    convo = provider.start(SYSTEM, TOOLS)
    scanner_desc = ws.scanner.description if ws.scanner.available else "unavailable"
    message: str | None = task_prompt(render_finding(ws.finding), policy_notes(ws), ws.test_command, scanner_desc)
    results: list[ToolResult] | None = None
    try:
        while run.turns < max_turns:
            run.turns += 1
            turn = convo.send(user=message, tool_results=results)
            message, results = None, None
            run.usage.add(turn.usage)
            served = turn.model or provider.model
            if served not in run.models_used:
                run.models_used.append(served)
            run.cost_usd = cost_usd(provider.name, provider.model, run.usage, pricing)
            if on_event:
                on_event("turn", {"turn": run.turns, "tools": [c.name for c in turn.tool_calls]})
            if turn.stop == "refusal":
                run.status, run.final_text = "refused", turn.text
                break
            if not turn.tool_calls:
                if ws.submission:
                    break
                run.final_text = turn.text
                message = (
                    "Continue using the tools. When the fix is complete call submit; "
                    "if you cannot fix it safely call give_up."
                )
                continue
            results = []
            for call in turn.tool_calls:
                out, is_error = ws.call(call.name, call.arguments)
                results.append(ToolResult(call.id, call.name, out[:60_000], is_error))
            if ws.submission:
                break
            over_tokens = run.usage.total > max_tokens
            over_cost = max_usd is not None and run.cost_usd is not None and run.cost_usd > max_usd
            if over_tokens or over_cost:
                run.status = "budget_exhausted"
                run.error = f"stopped at {run.usage.total} tokens" + (
                    f" / ${run.cost_usd:.2f}" if run.cost_usd is not None else ""
                )
                break
        else:
            run.status = "budget_exhausted"
            run.error = f"no submission after {max_turns} turns"
    except ProviderError as exc:
        run.status, run.error = "error", str(exc)
    if ws.submission:
        run.status = "disputed" if ws.submission.disputed else ("gave_up" if ws.submission.gave_up else "submitted")
    run.duration_s = round(time.monotonic() - start, 1)
    run.tool_log = ws.log
    return run
