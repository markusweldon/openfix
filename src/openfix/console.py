"""Terminal output: colour when writing to a terminal, plain text otherwise (and with NO_COLOR)."""

from __future__ import annotations

import os
import sys
from typing import TextIO

from .findings import Finding

_CODES = {"bold": "1", "dim": "2", "red": "31", "green": "32", "yellow": "33", "magenta": "35"}
_TOOLS = {"snykcode": "Snyk Code", "snyk open source": "Snyk Open Source", "semgrep oss": "Semgrep"}
_SEVERITY = {"critical": "red", "high": "red", "medium": "yellow", "low": "dim", "info": "dim"}
_GLYPH = {"passed": ("✔", "green"), "failed": ("✘", "red")}
_STATUS = {"verified": "green", "skipped": "dim", "unverified": "yellow"}


def color_enabled(stream: TextIO) -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    return bool(getattr(stream, "isatty", lambda: False)())


def paint(text: str, *styles: str, stream: TextIO | None = None) -> str:
    if not styles or not color_enabled(stream or sys.stderr):
        return text
    return "\033[" + ";".join(_CODES[s] for s in styles) + "m" + text + "\033[0m"


def tool_label(tool: str) -> str:
    return _TOOLS.get(tool.lower(), tool)


def finding_line(f: Finding) -> str:
    """One line per finding: scanner, severity, what it is, where."""
    title = f.title if f.title and not f.title.lower().startswith(f"{f.tool.lower().split()[0]} finding") else ""
    what = title or f.rule_id
    where = ""
    if f.location:
        where = f.location.path + (f":{f.location.start_line}" if f.location.start_line else "")
    elif f.package:
        where = f"{f.package.name}@{f.package.version or '?'}"
    sev = f.severity.value
    return "  ".join(
        x
        for x in (
            "→ " + paint(f"{tool_label(f.tool):<9}", "bold"),
            paint(f"{sev:<6}", _SEVERITY.get(sev, "dim")),
            what,
            paint(where, "dim"),
        )
        if x
    )


def result_line(status: str, detail: str, checks: list[tuple[str, str]], pr_url: str | None = None) -> str:
    """The checks that ran, then the outcome; the detail is shown when the fix did not verify."""
    parts = []
    for name, st in checks:
        glyph, color = _GLYPH.get(st, ("·", "dim"))
        parts.append(paint(f"{glyph} {name.replace('_', ' ')}", color))
    line = "  " + "   ".join(parts + [paint(f"→ {status}", "bold", _STATUS.get(status, "red"))])
    if pr_url:
        line += f"  {pr_url}"
    if status != "verified" and detail:
        line += "\n    " + paint(detail, "dim")
    return line
