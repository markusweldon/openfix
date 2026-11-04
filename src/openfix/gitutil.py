"""Thin, hardened wrappers around git."""

from __future__ import annotations

import os
import subprocess
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from pathlib import Path


class GitError(RuntimeError):
    pass


def git(repo: Path | str, *args: str, check: bool = True, input: str | None = None) -> str:
    env = {k: v for k, v in os.environ.items() if k in ("PATH", "HOME", "LANG", "TMPDIR", "SSH_AUTH_SOCK")}
    env.update({"GIT_TERMINAL_PROMPT": "0", "GIT_CONFIG_NOSYSTEM": "1", "LC_ALL": "C"})
    res = subprocess.run(
        ["git", "-C", str(repo), "-c", "core.hooksPath=/dev/null", *args],
        capture_output=True,
        text=True,
        env=env,
        input=input,
        timeout=300,
    )
    if check and res.returncode != 0:
        raise GitError(f"git {' '.join(args)} failed: {res.stderr.strip() or res.stdout.strip()}")
    return res.stdout


def repo_root(path: Path | str) -> Path:
    return Path(git(path, "rev-parse", "--show-toplevel").strip())


def head_commit(repo: Path | str) -> str:
    return git(repo, "rev-parse", "HEAD").strip()


def is_dirty(repo: Path | str) -> bool:
    return bool(git(repo, "status", "--porcelain", "--untracked-files=no").strip())


@contextmanager
def worktree(repo: Path | str, commit: str, keep: bool = False) -> Iterator[Path]:
    """A detached, disposable checkout of ``commit``. The user's working tree is never touched."""
    base = Path(tempfile.mkdtemp(prefix="openfix-wt-"))
    path = base / "repo"
    git(repo, "worktree", "add", "--detach", "--force", str(path), commit)
    try:
        yield path
    finally:
        if not keep:
            git(repo, "worktree", "remove", "--force", str(path), check=False)
            git(repo, "worktree", "prune", check=False)
            with suppress(OSError):
                base.rmdir()


def diff_against(work: Path, base: str) -> str:
    """Unified diff of every change (including new files) in ``work`` relative to ``base``."""
    git(work, "add", "-A")
    return git(work, "diff", "--cached", "--binary", "--no-color", "--no-ext-diff", base)


def changed_files(work: Path, base: str) -> list[tuple[str, int, int]]:
    git(work, "add", "-A")
    rows = []
    # --relative: paths relative to (and limited to) ``work`` when it is a subdirectory of the checkout.
    for line in git(work, "diff", "--cached", "--numstat", "--relative", base).splitlines():
        added, removed, path = line.split("\t", 2)
        rows.append((path, int(added) if added.isdigit() else 0, int(removed) if removed.isdigit() else 0))
    return rows


def file_at(repo: Path, commit: str, path: str) -> str | None:
    try:
        return git(repo, "show", f"{commit}:{path}")
    except GitError:
        return None


def exclude_locally(work: Path, pattern: str) -> None:
    """Add an ignore pattern for this checkout only (never committed)."""
    common = Path(git(work, "rev-parse", "--path-format=absolute", "--git-common-dir").strip()).resolve()
    exclude = common / "info" / "exclude"
    if not (common / "HEAD").is_file():
        raise GitError(f"unexpected git directory {common}")
    exclude.parent.mkdir(parents=True, exist_ok=True)
    existing = exclude.read_text() if exclude.exists() else ""
    if pattern not in existing.splitlines():
        exclude.write_text(existing + ("" if existing.endswith("\n") or not existing else "\n") + pattern + "\n")
