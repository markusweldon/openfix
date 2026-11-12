"""Orchestration: findings -> policy decision -> isolated fix -> independent verification -> receipt -> PR."""

from __future__ import annotations

import hashlib
import json
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import providers
from .agent import Workspace, run_agent
from .console import finding_line, result_line
from .deps import try_bump
from .findings import Finding
from .github import PublishError, open_pull_request
from .gitutil import changed_files, diff_against, exclude_locally, file_at, head_commit, is_dirty, repo_root, worktree
from .policy import Action, Command, Decision, Policy
from .receipt import make_receipt, sha256, write_receipt
from .report import pr_body, summary_markdown
from .sandbox import Sandbox, make_sandbox
from .sarif_out import to_sarif
from .scanners import SCAN_DIR, Scanner, preset_for
from .verify import (
    Check,
    check_regression_test,
    check_rescan,
    check_review,
    check_tests,
    detect_setup_command,
    detect_test_command,
    overall,
    scan_target,
)


@dataclass
class Options:
    out: Path | None = None
    author: str | None = None
    reviewer: str | None = None
    sandbox: str | None = None
    open_prs: bool = False
    base_branch: str | None = None
    sign: bool = False
    dry_run: bool = False
    keep_worktrees: bool = False
    max_findings: int | None = None


@dataclass
class Outcome:
    finding: Finding
    decision: Decision
    status: str  # skipped | not_reproduced | verified | unverified | failed | no_fix | disputed | error
    detail: str = ""
    checks: list[Check] = field(default_factory=list)
    out_dir: Path | None = None
    pr_url: str | None = None
    cost_usd: float | None = None
    tokens: int = 0
    files: dict[str, tuple[str, str]] = field(default_factory=dict)
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.finding.id,
            "label": self.finding.short(),
            "action": self.decision.action.value,
            "rule": self.decision.rule,
            "status": self.status,
            "detail": self.detail,
            "checks": [c.to_dict() for c in self.checks],
            "out_dir": str(self.out_dir or ""),
            "pr_url": self.pr_url,
            "cost_usd": self.cost_usd,
            "tokens": self.tokens,
        }


Log = Callable[[str], None]


def _default_log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def scanner_spec(spec: Any, f: Finding) -> Any:
    """``verify.scanner`` may map scanner presets to commands; other tools fall back to their preset."""
    if isinstance(spec, dict):
        spec = spec.get(preset_for(f) or f.tool.lower())
    return spec


class Engine:
    def __init__(
        self, repo: Path, policy: Policy, options: Options, policy_path: Path | None = None, log: Log = _default_log
    ) -> None:
        self.repo = repo_root(repo)
        # Monorepos: findings, tests and scans are relative to the project directory, patches to the repo root.
        self.subdir = Path(repo).resolve().relative_to(self.repo.resolve()).as_posix()
        self.project = self.repo if self.subdir == "." else self.repo / self.subdir
        self.policy = policy
        self.opt = options
        self.log = log
        self.base = head_commit(self.repo)
        self.run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.out = options.out or (self.project / ".openfix" / "runs" / self.run_id)
        self.policy_digest = sha256(policy_path.read_bytes()) if policy_path else sha256(policy.model_dump_json())
        self._providers: dict[str, providers.Provider] = {}
        self._sandbox: Sandbox | None = None
        self.spent_usd = 0.0
        self.spent_tokens = 0

    # ---------------------------------------------------------------- helpers

    def provider(self, ref: str) -> providers.Provider:
        if ref not in self._providers:
            self._providers[ref] = providers.create(ref, effort=self.policy.models.effort)
        return self._providers[ref]

    @property
    def sandbox(self) -> Sandbox:
        if self._sandbox is None:
            sb = self.policy.sandbox
            self._sandbox = make_sandbox(self.opt.sandbox or sb.backend, self.project, sb.image, sb.memory, sb.cpus)
        return self._sandbox

    def to_repo(self, p: str) -> str:
        return p if self.subdir == "." else f"{self.subdir}/{p}"

    def to_project(self, p: str) -> str:
        if self.subdir == ".":
            return p
        prefix = self.subdir + "/"
        return p[len(prefix) :] if p.startswith(prefix) else "../" * len(Path(self.subdir).parts) + p

    def plan(self, findings: list[Finding]) -> list[tuple[Finding, Decision]]:
        ordered = sorted(findings, key=lambda f: (-f.severity.rank, f.tool, f.rule_id))
        return [(f, self.policy.decide(f)) for f in ordered]

    # ---------------------------------------------------------------- run

    def run(self, findings: list[Finding]) -> list[Outcome]:
        if is_dirty(self.repo):
            self.log(f"note: uncommitted changes are ignored; OpenFix works from the last commit ({self.base[:12]}).")
        if self.subdir != "." and file_at(self.repo, self.base, self.subdir) is None:
            raise ValueError(
                f"{self.subdir}/ is not in the last commit ({self.base[:12]}). OpenFix works from committed code; "
                "commit the project first."
            )
        plan = self.plan(findings)
        if not self.opt.dry_run:
            # Fail fast on a missing SDK or credential, before any worktree is created.
            refs = {self.opt.author or d.author for f, d in plan if d.action is not Action.skip and not f.package}
            for ref in sorted(refs):
                self.provider(ref)
        outcomes: list[Outcome] = []
        attempted = 0
        author_ref = self.opt.author or self.policy.models.author
        for f, d in plan:
            if self.opt.author:
                d.author = self.opt.author
            if d.action is Action.skip:
                outcomes.append(Outcome(f, d, "skipped", d.reason or f"policy rule '{d.rule}'"))
                continue
            if self.opt.max_findings is not None and attempted >= self.opt.max_findings:
                outcomes.append(Outcome(f, d, "skipped", "--max limit reached"))
                continue
            limit = self.policy.budgets.max_usd_per_run
            if limit is not None and self.spent_usd >= limit:
                outcomes.append(Outcome(f, d, "skipped", f"run budget of ${limit:.2f} spent"))
                continue
            attempted += 1
            self.log(finding_line(f))
            try:
                o = self.fix_one(f, d)
            except Exception as exc:  # noqa: BLE001 - one bad finding must not stop the run
                o = Outcome(f, d, "error", f"{type(exc).__name__}: {exc}")
            self.spent_usd += o.cost_usd or 0.0
            self.spent_tokens += o.tokens
            self.log(result_line(o.status, o.detail, [(c.name, c.status) for c in o.checks], o.pr_url))
            outcomes.append(o)
        self.write_summary(outcomes, author_ref)
        return outcomes

    def fix_one(self, f: Finding, d: Decision) -> Outcome:
        out_dir = (self.out / f.id).resolve()
        if out_dir.parent != self.out.resolve():
            raise ValueError(f"unsafe finding id {f.id!r}")
        required = list(d.require)
        if self.opt.dry_run:
            return Outcome(f, d, "skipped", "dry run")
        with worktree(self.repo, self.base, keep=self.opt.keep_worktrees) as work:
            proj = work if self.subdir == "." else work / self.subdir
            for pattern in (f"{SCAN_DIR}/", "node_modules/", ".venv/", "__pycache__/"):
                exclude_locally(work, pattern)
            vcfg = self.policy.verify
            setup = vcfg.setup.command if vcfg.setup else detect_setup_command(proj)
            test_cmd = vcfg.tests.command if vcfg.tests else detect_test_command(proj)
            spec = scanner_spec(vcfg.scanner, f)
            scanner = Scanner(spec.model_dump() if isinstance(spec, Command) else spec, f)

            # 1. Baseline on the original code.
            base_scan = scan_target(scanner, proj, f) if scanner.available else None
            if base_scan and not base_scan[0].error and not base_scan[1] and "rescan" in required:
                return Outcome(
                    f,
                    d,
                    "not_reproduced",
                    f"{scanner.description} does not report this finding at {self.base[:12]}; "
                    "nothing to fix (stale or environment-specific finding).",
                    checks=[check_rescan(base_scan, base_scan, scanner)],
                )
            if setup and test_cmd:
                res = self.sandbox.run(setup, proj, timeout=vcfg.setup.timeout if vcfg.setup else 1200, network=True)
                if not res.ok:
                    self.log(f"  setup failed (exit {res.exit_code}); tests may fail")
            base_tests = self.sandbox.run(test_cmd, proj, timeout=900) if test_cmd else None

            # 2. Produce a change.
            author_info: dict[str, Any] | None = None
            summary, regression_test, fixer = "", None, "agent"
            dep = try_bump(proj, f) if f.package else None
            cost, tokens = None, 0
            if dep:
                fixer = "deterministic"
                summary = f"Upgrade `{dep.package}` from `{dep.old}` to `{dep.new}` in `{dep.manifest}`."
                if dep.lockfile_note and setup and "npm" in setup:
                    self.sandbox.run(
                        "npm install --package-lock-only --ignore-scripts --no-audit --no-fund",
                        proj,
                        timeout=900,
                        network=True,
                    )
                elif dep.lockfile_note:
                    summary += f" Note: {dep.lockfile_note}."
            else:
                if d.local_only and not self.provider(d.author).local:
                    return Outcome(
                        f,
                        d,
                        "skipped",
                        f"policy limits {f.location.path if f.location else 'this code'} "
                        "to local models; configure a local provider (e.g. ollama:...)",
                    )
                provider = self.provider(d.author)
                ws = Workspace(proj, self.base, f, self.policy, self.sandbox, test_cmd, scanner)
                b = self.policy.budgets
                remaining = None if b.max_usd_per_run is None else max(0.0, b.max_usd_per_run - self.spent_usd)
                cap = (
                    min(x for x in (b.max_usd_per_fix, remaining) if x is not None)
                    if (b.max_usd_per_fix is not None or remaining is not None)
                    else None
                )
                agent = run_agent(provider, ws, b.max_turns, b.max_tokens_per_fix, cap, self.policy.pricing)
                cost, tokens = agent.cost_usd, agent.usage.total
                author_info = {
                    "model": d.author,
                    "served_by": agent.models_used,
                    "turns": agent.turns,
                    "usage": {
                        "input_tokens": agent.usage.input_tokens,
                        "output_tokens": agent.usage.output_tokens,
                        "cache_read_tokens": agent.usage.cache_read_tokens,
                    },
                    "cost_usd": cost,
                    "duration_s": agent.duration_s,
                    "status": agent.status,
                }
                out_dir.mkdir(parents=True, exist_ok=True)
                (out_dir / "agent-log.json").write_text(
                    json.dumps(
                        {
                            "author": author_info,
                            "tools": agent.tool_log,
                            "final_text": agent.final_text,
                            "error": agent.error,
                        },
                        indent=2,
                    )
                )
                if agent.status != "submitted":
                    reason = ws.submission.summary if ws.submission else (agent.error or agent.final_text[:300])
                    status = (
                        "disputed" if agent.status == "disputed" else ("error" if agent.status == "error" else "no_fix")
                    )
                    return Outcome(
                        f, d, status, f"{agent.status}: {reason}", out_dir=out_dir, cost_usd=cost, tokens=tokens
                    )
                assert ws.submission is not None
                summary = ws.submission.summary + (
                    f"\n\nRoot cause: {ws.submission.root_cause}" if ws.submission.root_cause else ""
                )
                regression_test = ws.submission.regression_test

            # 3. Collect the exact patch and re-check guards (defence in depth).
            patch = diff_against(work, self.base)
            files = changed_files(work, self.base)
            if not patch.strip():
                return Outcome(f, d, "no_fix", "no change was produced", out_dir=out_dir, cost_usd=cost, tokens=tokens)
            violations = self.guard_violations(work, files, f)
            if violations:
                return Outcome(
                    f,
                    d,
                    "failed",
                    "policy guard: " + "; ".join(violations),
                    out_dir=out_dir,
                    cost_usd=cost,
                    tokens=tokens,
                )

            # 4. Independent verification on the patched code.
            # Keyed by project-relative path, like the finding and the scanner output.
            base_sources = {self.to_project(p): file_at(self.repo, self.base, p) or "" for p, _, _ in files}
            if f.location and f.location.path not in base_sources:
                base_sources[f.location.path] = file_at(self.repo, self.base, self.to_repo(f.location.path)) or ""
            head_scan = scan_target(scanner, proj, f, base_sources) if base_scan else None
            head_tests = self.sandbox.run(test_cmd, proj, timeout=900) if test_cmd else None
            checks = [check_rescan(base_scan, head_scan, scanner), check_tests(base_tests, head_tests, test_cmd)]
            checks.append(
                check_regression_test(
                    self.repo,
                    self.base,
                    proj,
                    regression_test,
                    test_cmd,
                    self.sandbox,
                    setup,
                    head_tests,
                    base_tests,
                    subdir=self.subdir,
                )
            )
            reviewer_ref = self.opt.reviewer or self.policy.models.reviewer
            if "review" in required or reviewer_ref:
                reviewer = None
                if reviewer_ref:
                    try:
                        reviewer = self.provider(reviewer_ref)
                    except providers.ProviderError as exc:
                        self.log(f"  reviewer unavailable: {exc}")
                checks.append(check_review(reviewer, f, patch, summary, d.author))
            status = overall(checks, required)

            # 5. Receipt.
            after = {
                self.to_project(p): (work / p).read_text(encoding="utf-8", errors="replace")
                if (work / p).exists()
                else ""
                for p, _, _ in files
            }
            file_pairs = {p: (base_sources.get(p, ""), text) for p, text in after.items()}
            receipt = make_receipt(
                finding=f.model_dump(mode="json", exclude={"raw"}),
                decision=d.model_dump(mode="json"),
                repo={"root": self.repo.name, "base_commit": self.base},
                patch=patch,
                files=files,
                author=author_info,
                checks=[c.to_dict() for c in checks],
                status=status,
                summary=summary,
                fixer=fixer,
                policy_digest=self.policy_digest,
            )
            paths = write_receipt(out_dir, receipt, patch, sign=self.opt.sign)
            receipt_digest = sha256(paths["receipt"].read_bytes())
            o = Outcome(
                f,
                d,
                status,
                _status_detail(checks, required),
                checks,
                out_dir,
                cost_usd=cost,
                tokens=tokens,
                files=file_pairs,
                summary=summary,
            )

            # 6. Pull request (autofix + verified only).
            if self.opt.open_prs and d.action is Action.autofix and status == "verified":
                pr = self.policy.pull_requests
                body = pr_body(receipt, receipt_digest)
                try:
                    o.pr_url = open_pull_request(
                        work,
                        branch=f"{pr.branch_prefix}{f.id}",
                        title=f"fix(security): {f.display_title()}"[:120],
                        body=body,
                        commit_message=f"fix(security): {f.display_title()}\n\n{summary}\n\nOpenFix-Receipt: "
                        f"sha256:{receipt_digest}",
                        labels=pr.labels,
                        draft=pr.draft,
                        base_branch=self.opt.base_branch,
                    )
                except PublishError as exc:
                    o.detail += f" (PR not opened: {exc})"
            elif self.opt.open_prs and status == "verified":
                o.detail += " (policy says propose: patch written, no PR)"
            (out_dir / "pr-body.md").write_text(pr_body(receipt, receipt_digest), encoding="utf-8")
            return o

    def guard_violations(self, work: Path, files: list[tuple[str, int, int]], f: Finding) -> list[str]:
        g = self.policy.guards
        v = []
        if len(files) > g.max_files_changed:
            v.append(f"{len(files)} files changed (limit {g.max_files_changed})")
        lines = sum(a + r for _, a, r in files)
        if lines > g.max_lines_changed:
            v.append(f"{lines} lines changed (limit {g.max_lines_changed})")
        for p, _, _ in files:
            if self.policy.is_protected(p):
                v.append(f"protected path modified: {p}")
        if not g.allow_new_dependencies:
            for p, _, _ in files:
                if Path(p).name == "package.json":
                    added = _new_npm_deps(file_at(self.repo, self.base, p), work / p)
                    if added:
                        v.append(f"new dependencies added to {p}: {', '.join(sorted(added))}")
        return v

    def write_summary(self, outcomes: list[Outcome], author: str) -> None:
        self.out.mkdir(parents=True, exist_ok=True)
        meta = {
            "run_id": self.run_id,
            "repo": str(self.repo),
            "base_commit": self.base,
            "author": author,
            "reviewer": self.opt.reviewer or self.policy.models.reviewer,
            "totals": {"tokens": self.spent_tokens, "cost_usd": round(self.spent_usd, 4)},
        }
        rows = [o.to_dict() for o in outcomes]
        (self.out / "summary.json").write_text(json.dumps({"meta": meta, "outcomes": rows}, indent=2))
        (self.out / "summary.md").write_text(summary_markdown(rows, meta))
        entries = [
            {
                "finding": o.finding,
                "status": o.status,
                "summary": o.summary,
                "files": o.files,
                "receipt": str(o.out_dir / "receipt.json") if o.out_dir else None,
            }
            for o in outcomes
            if o.status not in ("skipped",)
        ]
        (self.out / "openfix.sarif").write_text(json.dumps(to_sarif(entries), indent=2))


def _status_detail(checks: list[Check], required: list[str]) -> str:
    missing = [c.name for c in checks if c.name in required and c.status != "passed"]
    if not missing:
        return "all required checks passed (" + ", ".join(required) + ")"
    return "; ".join(f"{c.name}: {c.status}" for c in checks if c.name in missing)


def _new_npm_deps(before: str | None, after_path: Path) -> set[str]:
    def names(text: str | None) -> set[str]:
        if not text:
            return set()
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return set()
        return {k for s in ("dependencies", "devDependencies", "optionalDependencies") for k in (data.get(s) or {})}

    after = after_path.read_text(encoding="utf-8") if after_path.exists() else None
    return names(after) - names(before)


def digest(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()
