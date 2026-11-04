"""The only capabilities the model has. There is no shell, no network and no git.

Every write goes through ``Workspace.guard_write``; commands are limited to the
test and scan commands the policy defines.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..findings import Finding
from ..gitutil import changed_files
from ..policy import Policy
from ..providers import ToolSpec
from ..sandbox import Sandbox
from ..scanners import SCAN_DIR, Scanner, line_map, matches

SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".tox", "target", SCAN_DIR}
MAX_READ_BYTES = 256_000
MAX_LIST = 400


class ToolRefused(Exception):
    """A tool call was refused by policy; the message is shown to the model."""


@dataclass
class Submission:
    summary: str
    root_cause: str = ""
    regression_test: str | None = None
    confidence: str = "medium"
    gave_up: bool = False
    disputed: bool = False  # the agent believes the finding is a false positive


@dataclass
class Workspace:
    root: Path
    base_commit: str
    finding: Finding
    policy: Policy
    sandbox: Sandbox
    test_command: str | None
    scanner: Scanner
    base_sources: dict[str, str] = field(default_factory=dict)
    test_runs: int = 0
    scan_runs: int = 0
    submission: Submission | None = None
    log: list[dict[str, Any]] = field(default_factory=list)

    # ----------------------------------------------------------- path safety

    def resolve(self, rel: str) -> Path:
        if not isinstance(rel, str) or not rel.strip():
            raise ToolRefused("path must be a non-empty repository-relative string")
        rel = rel.strip().replace("\\", "/")
        while rel.startswith("./"):
            rel = rel[2:]
        if rel.startswith("/") or re.match(r"^[A-Za-z]:", rel):
            raise ToolRefused("use a path relative to the repository root")
        root = self.root.resolve()
        target = (root / rel).resolve()
        if target != root and root not in target.parents:
            raise ToolRefused(f"{rel} is outside the repository")
        parts = Path(rel).parts
        if parts and parts[0] in (".git", SCAN_DIR):
            raise ToolRefused(f"{rel} is not accessible")
        return target

    def relpath(self, p: Path) -> str:
        return p.resolve().relative_to(self.root.resolve()).as_posix()

    def guard_write(self, rel: str, new_content: str) -> Path:
        target = self.resolve(rel)
        rel = self.relpath(target)
        if self.policy.is_protected(rel):
            raise ToolRefused(f"{rel} is protected by policy (guards.protected_paths) and cannot be modified")
        if target.is_symlink():
            raise ToolRefused(f"{rel} is a symlink; OpenFix does not write through symlinks")
        g = self.policy.guards
        current = {p for p, _, _ in changed_files(self.root, self.base_commit)}
        if rel not in current and len(current) + 1 > g.max_files_changed:
            raise ToolRefused(
                f"policy allows at most {g.max_files_changed} changed files; already changed: {sorted(current)}"
            )
        return target

    def remember_base(self, rel: str, target: Path) -> None:
        if rel not in self.base_sources and target.exists():
            self.base_sources[rel] = target.read_text(encoding="utf-8", errors="replace")

    def diff_stats(self) -> tuple[int, int]:
        rows = changed_files(self.root, self.base_commit)
        return len(rows), sum(a + r for _, a, r in rows)

    # ----------------------------------------------------------- tools

    def t_list_files(self, path: str = ".", pattern: str | None = None) -> str:
        base = self.resolve(path) if path not in ("", ".") else self.root
        if not base.is_dir():
            raise ToolRefused(f"{path} is not a directory")
        out: list[str] = []
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".cache"))
            for name in sorted(filenames):
                rel = self.relpath(Path(dirpath) / name)
                if pattern and not Path(rel).match(pattern):
                    continue
                out.append(rel)
                if len(out) >= MAX_LIST:
                    return "\n".join(out) + f"\n...(stopped at {MAX_LIST} entries; narrow the path)"
        return "\n".join(out) or "(no files)"

    def t_read_file(self, path: str, start_line: int = 1, end_line: int | None = None) -> str:
        target = self.resolve(path)
        if not target.is_file():
            raise ToolRefused(f"{path} does not exist")
        if target.stat().st_size > MAX_READ_BYTES * 4:
            raise ToolRefused(f"{path} is too large to read ({target.stat().st_size} bytes)")
        lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
        start = max(1, int(start_line or 1))
        end = min(len(lines), int(end_line) if end_line else start + 799)
        body = "\n".join(f"{i:>5}| {lines[i - 1]}" for i in range(start, end + 1))
        more = f"\n...({len(lines) - end} more lines; read with start_line={end + 1})" if end < len(lines) else ""
        return (body + more)[:MAX_READ_BYTES] or "(empty file)"

    def t_search(self, pattern: str, path: str = ".", file_pattern: str | None = None) -> str:
        try:
            rx = re.compile(pattern)
        except re.error as exc:
            raise ToolRefused(f"invalid regular expression: {exc}") from None
        hits: list[str] = []
        for rel in self.t_list_files(path, file_pattern).splitlines():
            p = self.root / rel
            if not p.is_file() or p.stat().st_size > MAX_READ_BYTES:
                continue
            try:
                text = p.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for n, line in enumerate(text.splitlines(), 1):
                if rx.search(line):
                    hits.append(f"{rel}:{n}: {line.strip()[:240]}")
                    if len(hits) >= 150:
                        return "\n".join(hits) + "\n...(stopped at 150 matches)"
        return "\n".join(hits) or "(no matches)"

    def t_edit_file(self, path: str, old_text: str, new_text: str) -> str:
        target = self.resolve(path)
        if not target.is_file():
            raise ToolRefused(f"{path} does not exist; use write_file to create a file")
        text = target.read_text(encoding="utf-8")
        count = text.count(old_text) if old_text else 0
        if count == 0:
            raise ToolRefused("old_text was not found; read the file again and copy the exact text")
        if count > 1:
            raise ToolRefused(f"old_text appears {count} times; include more surrounding lines to make it unique")
        new = text.replace(old_text, new_text, 1)
        self.guard_write(path, new)
        self.remember_base(self.relpath(target), target)
        target.write_text(new, encoding="utf-8")
        return self._after_write(path)

    def t_write_file(self, path: str, content: str) -> str:
        target = self.guard_write(path, content)
        self.remember_base(self.relpath(target), target)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return self._after_write(path)

    def _after_write(self, path: str) -> str:
        files, lines = self.diff_stats()
        limit = self.policy.guards.max_lines_changed
        warn = f" WARNING: over the policy limit of {limit} changed lines; reduce the change." if lines > limit else ""
        return f"Wrote {path}. Change so far: {files} file(s), {lines} line(s).{warn}"

    def t_run_tests(self) -> str:
        if not self.test_command:
            return "No test command is configured or detectable for this repository."
        self.test_runs += 1
        if self.test_runs > 8:
            raise ToolRefused("test budget exhausted (8 runs); submit or give up")
        res = self.sandbox.run(self.test_command, self.root, timeout=900)
        status = "PASSED" if res.ok else ("TIMED OUT" if res.timed_out else f"FAILED (exit {res.exit_code})")
        return f"$ {self.test_command}\n{status} in {res.duration_s}s\n{res.tail(5000)}"

    def t_rescan(self) -> str:
        if not self.scanner.available:
            return f"Rescan unavailable: {self.scanner.description} is not installed or configured."
        self.scan_runs += 1
        if self.scan_runs > 6:
            raise ToolRefused("rescan budget exhausted (6 runs)")
        result = self.scanner.scan(self.root)
        if result.error:
            return f"Rescan failed: {result.error}"
        lm = None
        loc = self.finding.location
        if loc and loc.path in self.base_sources and (self.root / loc.path).exists():
            lm = line_map(self.base_sources[loc.path], (self.root / loc.path).read_text(encoding="utf-8"))
        still = [c for c in result.findings if matches(self.finding, c, lm)]
        if still:
            where = ", ".join(c.short() for c in still[:5])
            return f"The scanner STILL reports the finding: {where}"
        return f"The scanner no longer reports the finding ({len(result.findings)} other results in scope)."

    def t_submit(
        self, summary: str, root_cause: str = "", regression_test: str | None = None, confidence: str = "medium"
    ) -> str:
        files, lines = self.diff_stats()
        if files == 0:
            raise ToolRefused("there are no changes to submit; make the fix first, or call give_up")
        if lines > self.policy.guards.max_lines_changed:
            raise ToolRefused(
                f"the change is {lines} lines; policy allows {self.policy.guards.max_lines_changed}. Make it smaller."
            )
        if regression_test:
            rt = self.resolve(regression_test)
            if not rt.is_file():
                raise ToolRefused(f"regression_test {regression_test} does not exist")
            regression_test = self.relpath(rt)
        self.submission = Submission(
            summary=summary, root_cause=root_cause, regression_test=regression_test, confidence=confidence
        )
        return "Submitted. OpenFix will now verify the change independently."

    def t_give_up(self, reason: str, false_positive: bool = False) -> str:
        self.submission = Submission(summary=reason, gave_up=True, disputed=bool(false_positive))
        return "Recorded."

    # ----------------------------------------------------------- dispatch

    def call(self, name: str, args: dict[str, Any]) -> tuple[str, bool]:
        fn = getattr(self, f"t_{name}", None)
        if fn is None or name not in TOOL_NAMES:
            return f"Unknown tool {name}", True
        if "_invalid" in args:
            return "Tool arguments were not valid JSON; try again.", True
        try:
            out = fn(**args)
            self.log.append({"tool": name, "args": _short(args), "ok": True})
            return out, False
        except ToolRefused as exc:
            self.log.append({"tool": name, "args": _short(args), "ok": False, "refused": str(exc)})
            return f"Refused: {exc}", True
        except TypeError as exc:
            return f"Bad arguments for {name}: {exc}", True
        except (OSError, UnicodeDecodeError) as exc:
            return f"{name} failed: {exc}", True


def _short(args: dict[str, Any]) -> dict[str, Any]:
    return {k: (v if not isinstance(v, str) or len(v) < 200 else v[:200] + "...") for k, v in args.items()}


def _schema(props: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {"type": "object", "properties": props, "required": required, "additionalProperties": False}


STR = {"type": "string"}
INT = {"type": "integer"}

TOOLS: list[ToolSpec] = [
    ToolSpec(
        "list_files",
        "List repository files (skips .git, node_modules, build output).",
        _schema(
            {
                "path": {**STR, "description": "Directory, default '.'"},
                "pattern": {**STR, "description": "Optional glob such as '*.js'"},
            },
            [],
        ),
    ),
    ToolSpec(
        "read_file",
        "Read a file with line numbers. Reads up to 800 lines per call.",
        _schema({"path": STR, "start_line": INT, "end_line": INT}, ["path"]),
    ),
    ToolSpec(
        "search",
        "Regex search across repository files. Returns path:line: text.",
        _schema({"pattern": STR, "path": STR, "file_pattern": STR}, ["pattern"]),
    ),
    ToolSpec(
        "edit_file",
        "Replace one exact, unique occurrence of old_text with new_text in an existing file.",
        _schema({"path": STR, "old_text": STR, "new_text": STR}, ["path", "old_text", "new_text"]),
    ),
    ToolSpec(
        "write_file",
        "Create a file (for example a regression test) or overwrite one completely.",
        _schema({"path": STR, "content": STR}, ["path", "content"]),
    ),
    ToolSpec("run_tests", "Run the repository's test command in the sandbox and return the result.", _schema({}, [])),
    ToolSpec(
        "rescan",
        "Re-run the security scanner that reported the finding and say whether it still fires.",
        _schema({}, []),
    ),
    ToolSpec(
        "submit",
        "Finish with a fix. OpenFix then verifies it independently.",
        _schema(
            {
                "summary": {**STR, "description": "What changed and why it fixes the vulnerability"},
                "root_cause": STR,
                "regression_test": {**STR, "description": "Path of a test you added that fails without the fix"},
                "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
            },
            ["summary"],
        ),
    ),
    ToolSpec(
        "give_up",
        "Stop without a fix, e.g. when a safe fix needs a human decision or the finding is a "
        "false positive (explain the evidence).",
        _schema({"reason": STR, "false_positive": {"type": "boolean"}}, ["reason"]),
    ),
]
TOOL_NAMES = {t.name for t in TOOLS}


def render_finding(f: Finding) -> str:
    data: dict[str, Any] = {
        "tool": f.tool,
        "rule": f.rule_id,
        "title": f.title,
        "severity": f.severity.value,
        "category": f.category.value,
        "cwe": f.cwe,
        "advisories": f.advisories,
        "message": f.message[:4000],
    }
    if f.location:
        data["location"] = f.location.model_dump(exclude_none=True)
    if f.package:
        data["package"] = f.package.model_dump(exclude_none=True)
    if f.help_uri:
        data["help"] = f.help_uri
    return json.dumps(data, indent=2)
