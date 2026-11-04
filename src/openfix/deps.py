"""Deterministic dependency upgrades. No model is involved when a direct dependency can simply be bumped.

Supported manifests: package.json (npm/yarn/pnpm), requirements*.txt (pip). Anything else - transitive
dependencies, other ecosystems, upgrades needing code changes - goes to the agent.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from .findings import Finding


def _vkey(v: str) -> tuple:
    parts = re.split(r"[.\-+]", v.strip().lstrip("v=^~<>"))
    key: list[tuple[int, int | str]] = []
    for p in parts:
        key.append((0, int(p)) if p.isdigit() else (1, p))
    return tuple(key)


def choose_fixed_version(current: str | None, fixed: list[str]) -> str | None:
    """Lowest fixed version above ``current``, preferring one in the same major version."""
    cands = sorted({f.strip().lstrip("v=^~<>") for f in fixed if f and re.match(r"^[v=^~<>]*\d", f.strip())}, key=_vkey)
    if not cands:
        return None
    if current:
        cur = current.strip().lstrip("v=^~<>")
        above = [c for c in cands if _vkey(c) > _vkey(cur)]
        major = cur.split(".")[0]
        same_major = [c for c in above if c.split(".")[0] == major]
        picked = same_major or above
        return picked[0] if picked else None
    return cands[0]


@dataclass
class DepFix:
    manifest: str
    package: str
    old: str
    new: str
    lockfile_note: str | None = None


def try_bump(work: Path, f: Finding) -> DepFix | None:
    pkg = f.package
    if not pkg or not pkg.name:
        return None
    target = choose_fixed_version(pkg.version, pkg.fixed_versions)
    if not target:
        return None
    manifests = [pkg.manifest] if pkg.manifest else []
    eco = (pkg.ecosystem or "").lower()
    if not manifests:
        manifests = ["package.json"] if eco in ("npm", "yarn", "pnpm", "node") else ["requirements.txt"]
    for m in manifests:
        path = work / m
        if not path.is_file():
            continue
        if path.name == "package.json":
            return _bump_npm(path, m, pkg.name, target, work)
        if path.name.startswith("requirements") and path.suffix == ".txt":
            return _bump_pip(path, m, pkg.name, target)
    return None


def _bump_npm(path: Path, rel: str, name: str, target: str, work: Path) -> DepFix | None:
    text = path.read_text(encoding="utf-8")
    data = json.loads(text)
    for section in ("dependencies", "devDependencies", "optionalDependencies", "peerDependencies"):
        spec = (data.get(section) or {}).get(name)
        if not isinstance(spec, str):
            continue
        m = re.match(r"^(\^|~|>=|=)?\s*v?(\d[\w.\-+]*)$", spec.strip())
        if not m:
            return None  # ranges, tags, git URLs: leave to the agent
        prefix = m.group(1) or ""
        if _vkey(m.group(2)) >= _vkey(target):
            return None
        new_spec = f"{prefix}{target}"
        # Edit textually so formatting and key order are preserved.
        pattern = re.compile(r'("' + re.escape(name) + r'"\s*:\s*")' + re.escape(spec) + '"')
        new_text, n = pattern.subn(r"\g<1>" + new_spec.replace("\\", "\\\\") + '"', text, count=1)
        if n != 1:
            return None
        path.write_text(new_text, encoding="utf-8")
        note = None
        for lock in ("package-lock.json", "yarn.lock", "pnpm-lock.yaml"):
            if (path.parent / lock).exists():
                note = f"{lock} must be regenerated (e.g. npm install --package-lock-only)"
        return DepFix(rel, name, spec, new_spec, note)
    return None


def _bump_pip(path: Path, rel: str, name: str, target: str) -> DepFix | None:
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    norm = re.sub(r"[-_.]+", "-", name).lower()
    for i, line in enumerate(lines):
        m = re.match(r"^(\s*)([A-Za-z0-9_.\-]+)(\[[^\]]*\])?\s*(==|>=|~=)\s*([\w.\-+]+)(.*)$", line.rstrip("\n"))
        if not m or re.sub(r"[-_.]+", "-", m.group(2)).lower() != norm:
            continue
        if _vkey(m.group(5)) >= _vkey(target):
            return None
        old = f"{m.group(4)}{m.group(5)}"
        lines[i] = f"{m.group(1)}{m.group(2)}{m.group(3) or ''}{m.group(4)}{target}{m.group(6)}\n"
        path.write_text("".join(lines), encoding="utf-8")
        return DepFix(rel, name, old, f"{m.group(4)}{target}")
    return None
