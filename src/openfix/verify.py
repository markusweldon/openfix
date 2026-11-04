"""Independent verification. Nothing here trusts the model's account of what it did."""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .agent.prompts import REVIEW_SYSTEM, review_prompt
from .agent.tools import render_finding
from .findings import Finding
from .gitutil import file_at, worktree
from .providers import Provider, ProviderError
from .redact import redact_text
from .sandbox import CommandResult, Sandbox
from .scanners import Scanner, ScanResult, line_map, matches

PASSED, FAILED, NOT_RUN, INCONCLUSIVE = "passed", "failed", "not_run", "inconclusive"


@dataclass
class Check:
    name: str
    status: str
    detail: str
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _cmd_evidence(res: CommandResult | None) -> dict[str, Any]:
    if res is None:
        return {}
    return {
        "command": res.command,
        "exit_code": res.exit_code,
        "duration_s": res.duration_s,
        "timed_out": res.timed_out,
        "output_tail": res.tail(1500),
    }


def detect_test_command(repo: Path) -> str | None:
    pkg = repo / "package.json"
    if pkg.is_file():
        try:
            scripts = json.loads(pkg.read_text(encoding="utf-8")).get("scripts") or {}
        except json.JSONDecodeError:
            scripts = {}
        test = scripts.get("test", "")
        if test and "no test specified" not in test:
            return "npm test --silent"
    has_py = (repo / "pyproject.toml").is_file() or (repo / "pytest.ini").is_file() or (repo / "tests").is_dir()
    if has_py and (any(repo.rglob("test_*.py")) or any(repo.rglob("*_test.py"))):
        return "python -m pytest -q -x"
    if (repo / "go.mod").is_file():
        return "go test ./..."
    if (repo / "Cargo.toml").is_file():
        return "cargo test --quiet"
    if (repo / "pom.xml").is_file():
        return "mvn -q -B test"
    if (repo / "build.gradle").is_file() or (repo / "build.gradle.kts").is_file():
        return "./gradlew test --quiet"
    return None


def detect_setup_command(repo: Path) -> str | None:
    if (repo / "package.json").is_file() and not (repo / "node_modules").exists():
        if (repo / "package-lock.json").exists():
            return "npm ci --ignore-scripts --no-audit --no-fund"
        if (repo / "pnpm-lock.yaml").exists():
            return "corepack pnpm install --frozen-lockfile --ignore-scripts"
        if (repo / "yarn.lock").exists():
            return "corepack yarn install --frozen-lockfile --ignore-scripts"
        deps = json.loads((repo / "package.json").read_text(encoding="utf-8"))
        if deps.get("dependencies") or deps.get("devDependencies"):
            return "npm install --ignore-scripts --no-audit --no-fund"
    return None


# ----------------------------------------------------------------------------- rescan


def scan_target(
    scanner: Scanner, work: Path, finding: Finding, base_sources: dict[str, str] | None = None
) -> tuple[ScanResult, list[Finding]]:
    result = scanner.scan(work)
    lm = None
    loc = finding.location
    if base_sources is not None and loc and loc.path in base_sources and (work / loc.path).exists():
        lm = line_map(base_sources[loc.path], (work / loc.path).read_text(encoding="utf-8", errors="replace"))
    return result, [c for c in result.findings if matches(finding, c, lm)]


def check_rescan(
    base: tuple[ScanResult, list[Finding]] | None, head: tuple[ScanResult, list[Finding]] | None, scanner: Scanner
) -> Check:
    if base is None or head is None:
        return Check("rescan", NOT_RUN, f"Scanner unavailable ({scanner.description})")
    (b_res, b_hits), (h_res, h_hits) = base, head
    ev = {
        "scanner": scanner.description,
        "base_matches": [f.short() for f in b_hits],
        "head_matches": [f.short() for f in h_hits],
        "base_total": len(b_res.findings),
        "head_total": len(h_res.findings),
        "base_run": _cmd_evidence(b_res.command),
        "head_run": _cmd_evidence(h_res.command),
    }
    if b_res.error or h_res.error:
        return Check("rescan", NOT_RUN, f"Scanner error: {b_res.error or h_res.error}", ev)
    if not b_hits:
        return Check(
            "rescan",
            INCONCLUSIVE,
            "The scanner did not reproduce the finding on the original code, so its absence after the "
            "patch proves nothing.",
            ev,
        )
    if h_hits:
        return Check("rescan", FAILED, "The scanner still reports the finding on the patched code.", ev)
    return Check("rescan", PASSED, "Reproduced on the original code; not reported on the patched code.", ev)


# ----------------------------------------------------------------------------- tests


def check_tests(base_run: CommandResult | None, head_run: CommandResult | None, command: str | None) -> Check:
    if not command or head_run is None:
        return Check("tests", NOT_RUN, "No test command configured or detected.")
    ev = {"head_run": _cmd_evidence(head_run), "base_run": _cmd_evidence(base_run)}
    if head_run.ok:
        return Check("tests", PASSED, f"`{command}` passes on the patched code.", ev)
    if base_run is not None and not base_run.ok:
        return Check(
            "tests",
            INCONCLUSIVE,
            f"`{command}` fails on the patched code, but it already failed on the original code.",
            ev,
        )
    return Check("tests", FAILED, f"`{command}` fails on the patched code but passed on the original.", ev)


def check_regression_test(
    repo: Path,
    base_commit: str,
    work: Path,
    test_path: str | None,
    command: str | None,
    sandbox: Sandbox,
    setup: str | None,
    head_tests: CommandResult | None,
    base_tests: CommandResult | None,
    subdir: str = ".",
) -> Check:
    """Differential proof: the new test must fail on the original code and pass on the patched code."""
    if not test_path:
        return Check("regression_test", NOT_RUN, "The agent did not add a regression test.")
    if not command:
        return Check("regression_test", NOT_RUN, "No test command to run the regression test with.")
    if base_tests is not None and not base_tests.ok:
        return Check(
            "regression_test",
            INCONCLUSIVE,
            "The test suite already fails on the original code, so a failing run proves nothing.",
        )
    repo_path = test_path if subdir == "." else f"{subdir}/{test_path}"
    if file_at(repo, base_commit, repo_path) is not None:
        return Check(
            "regression_test", INCONCLUSIVE, f"{test_path} already existed; a differential check needs a new test file."
        )
    test_src = (work / test_path).resolve()
    if work.resolve() not in test_src.parents or not test_src.is_file() or test_src.is_symlink():
        return Check("regression_test", FAILED, f"{test_path} is not a regular file inside the checkout.")
    with worktree(repo, base_commit) as base_root:
        base = base_root if subdir == "." else base_root / subdir
        dest = (base / test_path).resolve()
        if base.resolve() not in dest.parents:
            return Check("regression_test", FAILED, f"{test_path} resolves outside the checkout.")
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(test_src, dest)
        if sandbox.kind == "local":
            _link_deps(work, base)
        if setup and not (base / "node_modules").exists():
            sandbox.run(setup, base, timeout=1200, network=True)
        before = sandbox.run(command, base, timeout=900)
    ev = {"test": test_path, "original_with_test": _cmd_evidence(before), "patched": _cmd_evidence(head_tests)}
    passes_after = head_tests is not None and head_tests.ok
    if before.ok:
        return Check(
            "regression_test",
            FAILED,
            f"{test_path} passes on the original code, so it does not demonstrate the vulnerability.",
            ev,
        )
    if not passes_after:
        return Check(
            "regression_test", FAILED, "The test suite (including the new test) fails on the patched code.", ev
        )
    return Check("regression_test", PASSED, f"{test_path} fails on the original code and passes with the fix.", ev)


def _link_deps(src: Path, dst: Path) -> None:
    """Reuse installed dependencies between checkouts instead of reinstalling."""
    for d in ("node_modules", ".venv", "vendor"):
        if (src / d).is_dir() and not (dst / d).exists():
            (dst / d).symlink_to((src / d).resolve(), target_is_directory=True)


# ----------------------------------------------------------------------------- review


def check_review(reviewer: Provider | None, finding: Finding, diff: str, summary: str, author: str) -> Check:
    if reviewer is None:
        return Check("review", NOT_RUN, "No reviewer model configured (models.reviewer).")
    ref = f"{reviewer.name}:{reviewer.model}"
    ev: dict[str, Any] = {"reviewer": ref, "author": author}
    try:
        convo = reviewer.start(REVIEW_SYSTEM, [])
        turn = convo.send(user=review_prompt(render_finding(finding), redact_text(diff[:120_000]), summary))
    except ProviderError as exc:
        return Check("review", NOT_RUN, f"Reviewer unavailable: {exc}", ev)
    ev["usage"] = {"input_tokens": turn.usage.input_tokens, "output_tokens": turn.usage.output_tokens}
    m = re.search(r"\{.*\}", turn.text, re.S)
    try:
        verdict = json.loads(m.group(0)) if m else {}
    except json.JSONDecodeError:
        verdict = {}
    if not isinstance(verdict, dict) or verdict.get("verdict") not in ("approve", "request_changes"):
        ev["raw"] = turn.text[:2000]
        return Check("review", INCONCLUSIVE, "Reviewer reply was not a valid verdict.", ev)
    ev["verdict"] = verdict
    same_vendor = ref.split(":")[0] == author.split(":")[0]
    note = " (same provider as the author)" if same_vendor else ""
    if verdict["verdict"] == "approve" and verdict.get("fixes_root_cause", True):
        return Check("review", PASSED, f"{ref} approved{note}: {verdict.get('summary', '')}".strip(), ev)
    concerns = "; ".join((verdict.get("bypasses") or []) + (verdict.get("concerns") or []))[:600]
    return Check("review", FAILED, f"{ref} requested changes{note}: {concerns or verdict.get('summary', '')}", ev)


def overall(checks: list[Check], required: list[str]) -> str:
    by = {c.name: c for c in checks}
    if any(c.status == FAILED for c in checks):
        return "failed"
    if all(by.get(r) is not None and by[r].status == PASSED for r in required):
        return "verified"
    return "unverified"
