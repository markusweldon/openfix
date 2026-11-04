"""Fix receipts: a self-contained, verifiable record of what was changed, by which model, under which
policy, and what independent evidence says about it.

A receipt is wrapped in an in-toto v1 Statement whose subject is the exact patch, so it can be signed with
Sigstore (``cosign attest-blob``) and checked later with ``openfix receipt verify``.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import __version__
from .gitutil import GitError, git

RECEIPT_TYPE = "https://github.com/markusweldon/openfix/receipt/v1"
STATEMENT_TYPE = "https://in-toto.io/Statement/v1"


def sha256(data: str | bytes) -> str:
    return hashlib.sha256(data.encode() if isinstance(data, str) else data).hexdigest()


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def build_statement(receipt: dict[str, Any], patch: str) -> dict[str, Any]:
    return {
        "_type": STATEMENT_TYPE,
        "subject": [{"name": "patch.diff", "digest": {"sha256": sha256(patch)}}],
        "predicateType": RECEIPT_TYPE,
        "predicate": receipt,
    }


def write_receipt(out_dir: Path, receipt: dict[str, Any], patch: str, sign: bool = False) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {"patch": out_dir / "patch.diff", "receipt": out_dir / "receipt.json"}
    paths["patch"].write_text(patch, encoding="utf-8")
    statement = build_statement(receipt, patch)
    paths["receipt"].write_text(json.dumps(statement, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    if sign:
        bundle = out_dir / "receipt.sigstore.json"
        if shutil.which("cosign"):
            res = subprocess.run(
                ["cosign", "sign-blob", "--yes", "--bundle", str(bundle), str(paths["receipt"])],
                capture_output=True,
                text=True,
                timeout=300,
            )
            if res.returncode == 0:
                paths["signature"] = bundle
            else:
                (out_dir / "signing-error.txt").write_text(res.stderr[-4000:], encoding="utf-8")
        else:
            (out_dir / "signing-error.txt").write_text("cosign is not installed; receipt left unsigned\n")
    return paths


def verify_receipt(path: Path, repo: Path | None = None) -> list[tuple[str, bool, str]]:
    """Re-check a receipt offline. Returns (check, ok, detail) rows."""
    path = Path(path)
    receipt_file = path / "receipt.json" if path.is_dir() else path
    patch_file = receipt_file.parent / "patch.diff"
    rows: list[tuple[str, bool, str]] = []
    statement = json.loads(receipt_file.read_text(encoding="utf-8"))
    rows.append(
        (
            "statement type",
            statement.get("_type") == STATEMENT_TYPE and statement.get("predicateType") == RECEIPT_TYPE,
            statement.get("predicateType", "?"),
        )
    )
    pred = statement.get("predicate") or {}
    if not patch_file.is_file():
        rows.append(("patch present", False, f"{patch_file} not found"))
        return rows
    patch = patch_file.read_text(encoding="utf-8")
    want = (statement.get("subject") or [{}])[0].get("digest", {}).get("sha256")
    rows.append(("patch digest", sha256(patch) == want, f"sha256 {sha256(patch)[:16]}..."))
    rows.append(("predicate digest", pred.get("patch", {}).get("sha256") == want, "predicate.patch.sha256"))
    if repo is not None:
        base = pred.get("repository", {}).get("base_commit")
        try:
            git(repo, "cat-file", "-e", f"{base}^{{commit}}")
            rows.append(("base commit exists", True, base or "?"))
        except GitError:
            rows.append(("base commit exists", False, f"{base} not found in {repo}"))
            return rows
        res = subprocess.run(
            ["git", "-C", str(repo), "apply", "--check", "-"], input=patch, capture_output=True, text=True
        )
        rows.append(("patch applies to repo", res.returncode == 0, (res.stderr or "ok").strip()[:200]))
    sig = receipt_file.parent / "receipt.sigstore.json"
    if sig.exists():
        rows.append(
            (
                "signature bundle",
                True,
                "present - verify with: cosign verify-blob --bundle "
                f"{sig} --certificate-identity <id> --certificate-oidc-issuer <issuer> {receipt_file}",
            )
        )
    return rows


def make_receipt(
    *,
    finding: dict[str, Any],
    decision: dict[str, Any],
    repo: dict[str, Any],
    patch: str,
    files: list[tuple[str, int, int]],
    author: dict[str, Any] | None,
    checks: list[dict[str, Any]],
    status: str,
    summary: str,
    fixer: str,
    policy_digest: str | None,
) -> dict[str, Any]:
    return {
        "openfix_version": __version__,
        "created_at": now(),
        "status": status,  # verified | unverified | failed
        "finding": finding,
        "policy": {"decision": decision, "policy_sha256": policy_digest},
        "repository": repo,
        "patch": {
            "sha256": sha256(patch),
            "files": [{"path": p, "added": a, "removed": r} for p, a, r in files],
            "lines_changed": sum(a + r for _, a, r in files),
        },
        "fixer": fixer,  # "agent" or "deterministic"
        "author": author,
        "summary": summary,
        "checks": checks,
    }
