"""openfix command line."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .console import paint
from .engine import Engine, Options
from .ingest import UnsupportedFormat, load_files
from .policy import EXAMPLE_POLICY, load_policy
from .providers import ProviderError, describe_providers
from .receipt import verify_receipt
from .sandbox import SandboxUnavailable


def _rel(p: Path) -> str:
    try:
        return str(p.resolve().relative_to(Path.cwd().resolve()))
    except ValueError:
        return str(p)


def _table(rows: list[list[str]], header: list[str]) -> str:
    widths = [max(len(str(r[i])) for r in [header, *rows]) for i in range(len(header))]
    fmt = "  ".join(f"{{:<{w}}}" for w in widths)
    out = [fmt.format(*header), fmt.format(*["-" * w for w in widths])]
    out += [fmt.format(*[str(c) for c in r]) for r in rows]
    return "\n".join(out)


def cmd_findings(a: argparse.Namespace) -> int:
    findings = load_files(a.reports)
    if a.json:
        print(
            json.dumps(
                {"openfix": "findings/v1", "findings": [f.model_dump(mode="json", exclude={"raw"}) for f in findings]},
                indent=2,
            )
        )
        return 0
    rows = [
        [
            f.id,
            f.severity.value,
            f.category.value,
            f.tool,
            f.rule_id[-48:],
            (f.location.path + (f":{f.location.start_line}" if f.location.start_line else ""))
            if f.location
            else (f.package.name if f.package else ""),
        ]
        for f in findings
    ]
    print(_table(rows, ["id", "severity", "category", "tool", "rule", "where"]))
    print(f"\n{len(findings)} finding(s)")
    return 0


def cmd_plan(a: argparse.Namespace) -> int:
    policy, path = load_policy(a.policy, a.repo)
    findings = load_files(a.reports)
    engine = Engine(Path(a.repo), policy, Options(), path, log=lambda _m: None)
    rows = []
    for f, d in engine.plan(findings):
        rows.append([f.id, d.action.value, f.severity.value, f.short()[:70], d.rule[:48]])
    print(
        f"policy: {path or 'built-in defaults'}   author: {policy.models.author}"
        f"   reviewer: {policy.models.reviewer or '-'}   require: {', '.join(policy.verify.require)}\n"
    )
    print(_table(rows, ["id", "action", "severity", "finding", "rule"]))
    counts: dict[str, int] = {}
    for r in rows:
        counts[r[1]] = counts.get(r[1], 0) + 1
    print("\n" + ", ".join(f"{v} {k}" for k, v in sorted(counts.items())))
    return 0


def cmd_fix(a: argparse.Namespace) -> int:
    policy, path = load_policy(a.policy, a.repo)
    if a.require:
        policy.verify.require = [x.strip() for x in a.require.split(",") if x.strip()]
        for r in policy.rules:
            r.require = None
    findings = load_files(a.reports)
    if a.only:
        wanted = {x.strip() for x in a.only.split(",")}
        findings = [f for f in findings if f.id in wanted or f.rule_id in wanted]
        if not findings:
            print(f"No findings match --only {a.only}", file=sys.stderr)
            return 2
    opts = Options(
        out=Path(a.out) if a.out else None,
        author=a.model,
        reviewer=a.reviewer,
        sandbox=a.sandbox,
        open_prs=a.open_prs,
        base_branch=a.base,
        sign=a.sign,
        dry_run=a.dry_run,
        keep_worktrees=a.keep_worktrees,
        max_findings=a.max,
    )
    engine = Engine(Path(a.repo), policy, opts, path)
    outcomes = engine.run(findings)
    by: dict[str, int] = {}
    for o in outcomes:
        by[o.status] = by.get(o.status, 0) + 1
    counts = ", ".join(f"{v} {k}" for k, v in sorted(by.items()))
    spent = f"tokens {engine.spent_tokens:,}   cost ${engine.spent_usd:.2f}"
    print(f"\n{paint(counts, 'bold', stream=sys.stdout)}   {spent}   results {_rel(engine.out)}")
    if a.fail_on_unfixed and any(o.status not in ("verified", "skipped") for o in outcomes):
        return 1
    return 0


def cmd_init(a: argparse.Namespace) -> int:
    target = Path(a.path)
    if target.exists() and not a.force:
        print(f"{target} already exists (use --force to overwrite)", file=sys.stderr)
        return 1
    target.write_text(EXAMPLE_POLICY, encoding="utf-8")
    print(f"wrote {target}")
    return 0


def cmd_providers(_a: argparse.Namespace) -> int:
    rows = [[r["provider"], r["example"], r["sdk"], r["credentials"]] for r in describe_providers()]
    print(_table(rows, ["provider", "example --model", "sdk", "credentials"]))
    return 0


def cmd_receipt_verify(a: argparse.Namespace) -> int:
    rows = verify_receipt(Path(a.path), Path(a.repo) if a.repo else None)
    for name, ok, detail in rows:
        print(f"{'ok  ' if ok else 'FAIL'}  {name:<24} {detail}")
    return 0 if all(ok for _, ok, _ in rows) else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="openfix", description="Model-agnostic security remediation. Every fix ships with proof."
    )
    p.add_argument("--version", action="version", version=f"openfix {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("findings", help="normalise scanner reports and list the findings")
    s.add_argument("reports", nargs="+")
    s.add_argument("--json", action="store_true", help="emit OpenFix findings JSON")
    s.set_defaults(fn=cmd_findings)

    s = sub.add_parser("plan", help="show what the policy will do with each finding (no model calls)")
    s.add_argument("reports", nargs="+")
    s.add_argument("--repo", default=".")
    s.add_argument("--policy")
    s.set_defaults(fn=cmd_plan)

    s = sub.add_parser("fix", help="fix findings, verify each fix, write receipts, optionally open PRs")
    s.add_argument("reports", nargs="+", help="SARIF / scanner JSON files")
    s.add_argument("--repo", default=".", help="git repository the findings refer to (default: .)")
    s.add_argument("--policy", help="policy file (default: openfix.yaml in the repo, else built-in)")
    s.add_argument("--model", help="author model as provider:model, overrides policy (e.g. openai:gpt-5)")
    s.add_argument("--reviewer", help="reviewer model as provider:model")
    s.add_argument(
        "--require", help="comma-separated required checks, overrides policy (rescan,tests,regression_test,review)"
    )
    s.add_argument("--only", help="comma-separated finding ids or rule ids")
    s.add_argument("--max", type=int, help="attempt at most N findings")
    s.add_argument("--sandbox", choices=["auto", "docker", "local"])
    s.add_argument("--open-prs", action="store_true", help="open a draft PR for each verified autofix")
    s.add_argument("--base", help="PR base branch (default: repository default branch)")
    s.add_argument("--sign", action="store_true", help="sign receipts with cosign (Sigstore)")
    s.add_argument("--out", help="output directory (default: .openfix/runs/<timestamp>)")
    s.add_argument("--dry-run", action="store_true")
    s.add_argument("--keep-worktrees", action="store_true", help=argparse.SUPPRESS)
    s.add_argument("--fail-on-unfixed", action="store_true", help="exit 1 unless every attempted fix verified")
    s.set_defaults(fn=cmd_fix)

    s = sub.add_parser("init", help="write a starter openfix.yaml")
    s.add_argument("path", nargs="?", default="openfix.yaml")
    s.add_argument("--force", action="store_true")
    s.set_defaults(fn=cmd_init)

    s = sub.add_parser("providers", help="list supported model providers and credential status")
    s.set_defaults(fn=cmd_providers)

    s = sub.add_parser("receipt", help="work with fix receipts")
    rs = s.add_subparsers(dest="receipt_cmd", required=True)
    v = rs.add_parser("verify", help="check a receipt's digests and that its patch applies")
    v.add_argument("path", help="receipt directory or receipt.json")
    v.add_argument("--repo", help="repository to check the patch against")
    v.set_defaults(fn=cmd_receipt_verify)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.fn(args) or 0)
    except (UnsupportedFormat, ProviderError, SandboxUnavailable, FileNotFoundError, ValueError) as exc:
        print(f"openfix: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
