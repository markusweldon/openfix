"""Re-running the original scanner to prove a finding is reproduced before and gone after a fix.

Static scanners read source; they do not execute it. They therefore run as local
processes (with a scrubbed environment) rather than inside the test sandbox, and
must be installed where OpenFix runs.
"""

from __future__ import annotations

import difflib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from .findings import Category, Finding
from .ingest import load_document
from .sandbox import CommandResult, LocalSandbox

SCAN_DIR = ".openfix-scan"


@dataclass(frozen=True)
class Preset:
    name: str
    binary: str
    command: str  # {output} -> SARIF path, {targets} -> space separated paths
    passthrough: tuple[str, ...] = ()
    per_file: bool = False


PRESETS: dict[str, Preset] = {
    "semgrep": Preset(
        "semgrep",
        "semgrep",
        "semgrep scan --config ${OPENFIX_SEMGREP_CONFIG:-p/default} --sarif --output {output} "
        "--metrics off --quiet --disable-version-check {targets}",
        passthrough=("SEMGREP_APP_TOKEN", "OPENFIX_SEMGREP_CONFIG"),
        per_file=True,
    ),
    "snyk-code": Preset(
        "snyk-code",
        "snyk",
        "snyk code test --sarif-file-output={output} . ; test -s {output}",
        passthrough=("SNYK_TOKEN", "SNYK_API"),
    ),
    "snyk": Preset(
        "snyk",
        "snyk",
        "snyk test --sarif-file-output={output} . ; test -s {output}",
        passthrough=("SNYK_TOKEN", "SNYK_API"),
    ),
    "trivy": Preset("trivy", "trivy", "trivy fs --quiet --scanners vuln,misconfig --format sarif --output {output} ."),
    "osv-scanner": Preset(
        "osv-scanner", "osv-scanner", "osv-scanner --format sarif --output {output} -r . ; test -s {output}"
    ),
    "gitleaks": Preset(
        "gitleaks", "gitleaks", "gitleaks dir . --report-format sarif --report-path {output} --exit-code 0"
    ),
    "bandit": Preset("bandit", "bandit", "bandit -q -f sarif -o {output} --exit-zero {targets}", per_file=True),
}


def preset_for(f: Finding) -> str | None:
    tool = f.tool.lower()
    if "semgrep" in tool:
        return "semgrep"
    if "snyk" in tool:
        return "snyk" if f.category is Category.sca else "snyk-code"
    for name in ("trivy", "osv-scanner", "gitleaks", "bandit"):
        if name.split("-")[0] in tool:
            return name
    return None


@dataclass
class ScanResult:
    findings: list[Finding]
    command: CommandResult | None
    error: str | None = None


class Scanner:
    def __init__(self, spec: str | dict | None, finding: Finding, timeout: int = 900) -> None:
        self.timeout = timeout
        self.preset: Preset | None = None
        self.command: str | None = None
        if isinstance(spec, dict):  # {command, timeout}
            self.command = spec["command"]
            self.timeout = int(spec.get("timeout", timeout))
        elif isinstance(spec, str) and spec in PRESETS:
            self.preset = PRESETS[spec]
        elif isinstance(spec, str) and spec:
            self.command = spec
        else:
            name = preset_for(finding)
            self.preset = PRESETS[name] if name else None
        self.finding = finding

    @property
    def available(self) -> bool:
        if self.command:
            return True
        return bool(self.preset and shutil.which(self.preset.binary))

    @property
    def description(self) -> str:
        if self.command:
            return self.command
        return self.preset.name if self.preset else "none"

    def scan(self, work: Path) -> ScanResult:
        if not self.available:
            why = f"{self.preset.binary} is not installed" if self.preset else "no scanner configured for this tool"
            return ScanResult([], None, why)
        out_dir = work / SCAN_DIR
        out_dir.mkdir(exist_ok=True)
        output = out_dir / "result.sarif"
        output.unlink(missing_ok=True)
        targets = "."
        loc = self.finding.location
        if self.preset and self.preset.per_file and loc and loc.path and (work / loc.path).exists():
            targets = _q(loc.path)
        template = self.command or (self.preset.command if self.preset else "")
        cmd = template.replace("{output}", _q(f"{SCAN_DIR}/result.sarif")).replace("{targets}", targets)
        res = LocalSandbox().run(
            cmd, work, timeout=self.timeout, passthrough=self.preset.passthrough if self.preset else ()
        )
        try:
            if not output.exists():
                return ScanResult([], res, f"scanner produced no SARIF (exit {res.exit_code}): {res.tail(800)}")
            doc = json.loads(output.read_text(encoding="utf-8"))
            return ScanResult(load_document(doc), res)
        except (ValueError, json.JSONDecodeError) as exc:
            return ScanResult([], res, f"could not read scanner output: {exc}")
        finally:
            shutil.rmtree(out_dir, ignore_errors=True)


def _q(s: str) -> str:
    return "'" + s.replace("'", "'\\''") + "'"


# ----------------------------------------------------------------------------- matching


def _same_rule(a: str, b: str) -> bool:
    if a == b:
        return True
    # Semgrep prefixes rule ids with the config path; compare the dotted tail.
    ta, tb = a.split(".")[-1], b.split(".")[-1]
    return ta == tb and (a.endswith(b) or b.endswith(a) or len(ta) > 12)


def matches(target: Finding, candidate: Finding, line_map: dict[int, int] | None = None, tolerance: int = 3) -> bool:
    """Does ``candidate`` (from a rescan) report the same problem as ``target``?"""
    if target.package and candidate.package:
        if target.package.name.lower() != candidate.package.name.lower():
            return False
        adv_t = set(a.upper() for a in target.advisories)
        adv_c = set(a.upper() for a in candidate.advisories) | {candidate.rule_id.upper()}
        return bool(adv_t & adv_c) or _same_rule(target.rule_id, candidate.rule_id)
    if not _same_rule(target.rule_id, candidate.rule_id):
        return False
    if not target.location or not candidate.location:
        return target.location is None and candidate.location is None
    if target.location.path != candidate.location.path:
        return False
    t_line, c_line = target.location.start_line, candidate.location.start_line
    if t_line is None or c_line is None:
        return True
    expected = line_map.get(t_line, t_line) if line_map else t_line
    return abs(expected - c_line) <= tolerance


def line_map(before: str, after: str) -> dict[int, int]:
    """Map 1-based line numbers in ``before`` to their position in ``after`` (deleted lines map to the
    nearest surviving position) so a finding can be followed across an edit."""
    a, b = before.splitlines(), after.splitlines()
    mapping: dict[int, int] = {}
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
        for k in range(i1, i2):
            if tag == "equal":
                mapping[k + 1] = j1 + (k - i1) + 1
            else:
                mapping[k + 1] = min(j1 + (k - i1), max(j2 - 1, j1)) + 1
    return mapping
