"""Write findings back out as SARIF 2.1.0 with ``fixes[]`` populated, so code-scanning UIs and other tools
can show (and apply) the proposed change next to the original alert."""

from __future__ import annotations

import difflib
from typing import Any

from . import __version__
from .findings import Finding


def replacements(before: str, after: str) -> list[dict[str, Any]]:
    a, b = before.splitlines(keepends=True), after.splitlines(keepends=True)
    out = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
        if tag == "equal":
            continue
        if i1 == i2:  # pure insertion: empty region at the start of line i1+1
            region = {"startLine": i1 + 1, "startColumn": 1, "endLine": i1 + 1, "endColumn": 1}
        else:
            region = {"startLine": i1 + 1, "startColumn": 1, "endLine": i2 + 1, "endColumn": 1}
        out.append({"deletedRegion": region, "insertedContent": {"text": "".join(b[j1:j2])}})
    return out


def to_sarif(entries: list[dict[str, Any]]) -> dict[str, Any]:
    """``entries``: dicts with ``finding``, ``status``, ``summary`` and ``files`` ({path: (before, after)})."""
    results = []
    for e in entries:
        f: Finding = e["finding"]
        result: dict[str, Any] = {
            "ruleId": f.rule_id,
            "level": {"critical": "error", "high": "error", "medium": "warning"}.get(f.severity.value, "note"),
            "message": {"text": f.title},
            "properties": {
                "openfix": {"id": f.id, "status": e.get("status"), "tool": f.tool, "receipt": e.get("receipt")}
            },
        }
        if f.location:
            region = {"startLine": f.location.start_line} if f.location.start_line else {}
            result["locations"] = [
                {
                    "physicalLocation": {
                        "artifactLocation": {"uri": f.location.path},
                        **({"region": region} if region else {}),
                    }
                }
            ]
        changes = [
            {"artifactLocation": {"uri": path}, "replacements": replacements(before, after)}
            for path, (before, after) in (e.get("files") or {}).items()
        ]
        if changes:
            result["fixes"] = [
                {"description": {"text": e.get("summary") or "OpenFix proposed fix"}, "artifactChanges": changes}
            ]
        results.append(result)
    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "OpenFix",
                        "version": __version__,
                        "informationUri": "https://github.com/markusweldon/openfix",
                    }
                },
                "results": results,
            }
        ],
    }
