"""Policy-as-code: what may be fixed, by whom, within which limits, and what proof is required.

The policy is evaluated by plain code outside the model. The model never sees
findings the policy skips, and every file write it attempts is checked against
the guards here.
"""

from __future__ import annotations

import re
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from .findings import Category, Finding, Severity

POLICY_FILENAMES = ("openfix.yaml", "openfix.yml", ".openfix.yaml", ".github/openfix.yaml")


class Action(str, Enum):
    autofix = "autofix"  # generate, verify, and open a pull request when every required check passes
    propose = "propose"  # generate and verify, but only write a patch + receipt for a human to apply
    skip = "skip"  # never sent to a model


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Match(Strict):
    tool: list[str] | None = None
    rule: list[str] | None = None  # glob on rule id
    category: list[Category] | None = None
    severity: list[Severity] | None = None
    min_severity: Severity | None = None
    cwe: list[str] | None = None
    path: list[str] | None = None  # glob on finding location

    def matches(self, f: Finding) -> bool:
        if self.tool and f.tool.lower() not in {t.lower() for t in self.tool}:
            return False
        if self.rule and not any(glob_match(p, f.rule_id) for p in self.rule):
            return False
        if self.category and f.category not in self.category:
            return False
        if self.severity and f.severity not in self.severity:
            return False
        if self.min_severity and f.severity.rank < self.min_severity.rank:
            return False
        if self.cwe and not set(c.upper() for c in self.cwe) & set(f.cwe):
            return False
        if self.path:
            target = (f.location.path if f.location else None) or (f.package.manifest if f.package else None)
            if not target or not any(glob_match(p, target) for p in self.path):
                return False
        return True


class Rule(Strict):
    name: str | None = None
    match: Match = Field(default_factory=Match)
    action: Action
    reason: str | None = None
    author: str | None = None  # override the author model for matching findings
    require: list[str] | None = None  # override verify.require


class Guards(Strict):
    max_files_changed: int = 4
    max_lines_changed: int = 200
    protected_paths: list[str] = Field(
        default_factory=lambda: [".git/**", ".github/workflows/**", "**/.env", "**/.env.*", "openfix.yaml"]
    )
    allow_test_files: bool = True  # the agent may add regression tests outside the finding's file
    allow_new_dependencies: bool = False


class Models(Strict):
    author: str = "anthropic:claude-opus-5-5"
    reviewer: str | None = None  # a model from a different provider is strongly recommended
    local_only_paths: list[str] = Field(default_factory=list)  # findings here may only use local providers
    effort: Literal["low", "medium", "high", "xhigh", "max"] | None = "high"


class Budgets(Strict):
    max_turns: int = 40
    max_tokens_per_fix: int = 600_000
    max_usd_per_fix: float | None = 3.0
    max_usd_per_run: float | None = 25.0


class Command(Strict):
    command: str
    timeout: int = 600


class Verify(Strict):
    require: list[Literal["rescan", "tests", "regression_test", "review"]] = Field(
        default_factory=lambda: ["rescan", "tests"]  # type: ignore[arg-type]
    )
    tests: Command | None = None  # auto-detected when omitted
    scanner: Command | str | None = None  # preset name (semgrep, osv-scanner, trivy, gitleaks) or command
    setup: Command | None = None  # e.g. "npm ci --ignore-scripts", run once before tests


class Sandbox(Strict):
    backend: Literal["auto", "docker", "local"] = "auto"
    image: str | None = None  # defaults per detected language
    network: bool = False
    memory: str = "2g"
    cpus: str = "2"


class PullRequests(Strict):
    draft: bool = True
    labels: list[str] = Field(default_factory=lambda: ["security", "openfix"])
    branch_prefix: str = "openfix/"
    group: Literal["per-finding", "per-rule", "single"] = "per-finding"


DEFAULT_RULES: list[dict[str, Any]] = [
    {
        "name": "secrets need rotation, not a code change",
        "match": {"category": ["secrets"]},
        "action": "skip",
        "reason": "A leaked credential must be rotated; removing it from code does not revoke it.",
    },
    {"name": "ignore informational results", "match": {"severity": ["info"]}, "action": "skip"},
    {
        "name": "infrastructure changes go to a human",
        "match": {"category": ["iac", "container"]},
        "action": "propose",
    },
    {
        "name": "security-sensitive code is reviewed before a PR",
        "match": {"path": ["**/auth/**", "**/crypto/**", "**/*crypt*", "**/iam/**", "**/payment*/**"]},
        "action": "propose",
    },
    {"name": "dependency upgrades", "match": {"category": ["sca"]}, "action": "autofix"},
    {"name": "code findings", "match": {"category": ["sast"], "min_severity": "low"}, "action": "autofix"},
]


class Policy(Strict):
    version: int = 1
    default_action: Action = Action.propose
    rules: list[Rule] = Field(default_factory=lambda: [Rule.model_validate(r) for r in DEFAULT_RULES])
    guards: Guards = Field(default_factory=Guards)
    models: Models = Field(default_factory=Models)
    budgets: Budgets = Field(default_factory=Budgets)
    verify: Verify = Field(default_factory=Verify)
    sandbox: Sandbox = Field(default_factory=Sandbox)
    pull_requests: PullRequests = Field(default_factory=PullRequests)
    pricing: dict[str, tuple[float, float]] = Field(default_factory=dict)  # model -> (usd/M in, usd/M out)

    # ------------------------------------------------------------------ decisions

    def decide(self, f: Finding) -> Decision:
        for i, rule in enumerate(self.rules):
            if rule.match.matches(f):
                return Decision(
                    finding_id=f.id,
                    action=rule.action,
                    rule=rule.name or f"rules[{i}]",
                    reason=rule.reason,
                    author=rule.author or self.models.author,
                    require=rule.require or list(self.verify.require),
                    local_only=self._local_only(f),
                )
        return Decision(
            finding_id=f.id,
            action=self.default_action,
            rule="default_action",
            author=self.models.author,
            require=list(self.verify.require),
            local_only=self._local_only(f),
        )

    def _local_only(self, f: Finding) -> bool:
        target = f.location.path if f.location else None
        return bool(target and any(glob_match(p, target) for p in self.models.local_only_paths))

    def is_protected(self, rel_path: str) -> bool:
        return any(glob_match(p, rel_path) for p in self.guards.protected_paths)


class Decision(BaseModel):
    finding_id: str
    action: Action
    rule: str
    reason: str | None = None
    author: str
    require: list[str]
    local_only: bool = False


def load_policy(path: str | Path | None = None, repo: str | Path | None = None) -> tuple[Policy, Path | None]:
    """Load an explicit policy file, else the first policy file found in the repo, else defaults."""
    candidates: list[Path] = []
    if path:
        candidates = [Path(path)]
    elif repo:
        candidates = [Path(repo) / name for name in POLICY_FILENAMES]
    for c in candidates:
        if c.is_file():
            data = yaml.safe_load(c.read_text(encoding="utf-8")) or {}
            if not isinstance(data, dict):
                raise ValueError(f"{c}: policy must be a mapping")
            return Policy.model_validate(data), c
    if path:
        raise FileNotFoundError(f"Policy file not found: {path}")
    return Policy(), None


@lru_cache(maxsize=512)
def _glob_regex(pattern: str) -> re.Pattern[str]:
    out, i = "", 0
    while i < len(pattern):
        c = pattern[i]
        if pattern.startswith("**/", i):
            out += "(?:.*/)?"
            i += 3
        elif pattern.startswith("**", i):
            out += ".*"
            i += 2
        elif c == "*":
            out += "[^/]*"
            i += 1
        elif c == "?":
            out += "[^/]"
            i += 1
        else:
            out += re.escape(c)
            i += 1
    return re.compile(f"^{out}$", re.IGNORECASE)


def glob_match(pattern: str, value: str) -> bool:
    """Glob with ``**`` support. Patterns without a slash also match the basename."""
    value = value.replace("\\", "/")
    while value.startswith("./"):
        value = value[2:]
    if _glob_regex(pattern).match(value):
        return True
    return "/" not in pattern and bool(_glob_regex(pattern).match(value.rsplit("/", 1)[-1]))


EXAMPLE_POLICY = """\
# OpenFix policy. Evaluated by code, never by the model.
# Docs: https://github.com/markusweldon/openfix/blob/main/docs/policy.md
version: 1
default_action: propose          # autofix | propose | skip

rules:                           # first match wins
  - name: secrets need rotation, not a code change
    match: { category: [secrets] }
    action: skip
  - name: ignore informational results
    match: { severity: [info] }
    action: skip
  - name: infrastructure changes go to a human
    match: { category: [iac, container] }
    action: propose
  - name: security-sensitive code is reviewed before a PR
    match: { path: ["**/auth/**", "**/crypto/**", "**/payment*/**"] }
    action: propose
  - name: dependency upgrades
    match: { category: [sca] }
    action: autofix
  - name: code findings
    match: { category: [sast], min_severity: low }
    action: autofix

guards:
  max_files_changed: 4
  max_lines_changed: 200
  protected_paths: [".git/**", ".github/workflows/**", "**/.env", "**/.env.*", "openfix.yaml"]
  allow_new_dependencies: false

models:
  author: anthropic:claude-opus-5-5   # provider:model - anthropic, openai, gemini, xai, openrouter, ollama, ...
  reviewer: openai:gpt-5              # optional second opinion from a different provider
  local_only_paths: []                # e.g. ["services/payments/**"] -> only local models see this code

budgets:
  max_turns: 40
  max_tokens_per_fix: 600000
  max_usd_per_fix: 3.0
  max_usd_per_run: 25.0

verify:
  require: [rescan, tests]            # also: regression_test, review
  # tests: { command: "npm test" }    # auto-detected when omitted
  # scanner: semgrep                  # preset, or { command: "... {output}" } writing SARIF to {output}

sandbox:
  backend: auto                       # docker when available; "local" runs commands on this machine
  network: false

pull_requests:
  draft: true
  labels: [security, openfix]
"""
