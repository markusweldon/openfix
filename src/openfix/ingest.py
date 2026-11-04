"""Turn scanner output into Findings.

Supported inputs (auto-detected):
  * SARIF 2.1.0 - Semgrep, CodeQL, Snyk Code, Trivy, Checkov, Bandit, gitleaks, ...
  * Semgrep JSON (``semgrep --json``)
  * Snyk Open Source JSON (``snyk test --json``)
  * Trivy JSON (``trivy fs --format json``)
  * OSV-Scanner JSON (``osv-scanner --format json``)
  * Gitleaks JSON report
  * GitHub code-scanning alerts and Dependabot alerts (REST API export)
  * OpenFix findings JSON (``{"openfix": "findings/v1", "findings": [...]}``)
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from .findings import Category, Finding, Location, Package, Severity, severity_from
from .redact import redact, redact_text

MAX_INPUT_BYTES = 64 * 1024 * 1024
CWE_RE = re.compile(r"CWE-\d+", re.IGNORECASE)
ADVISORY_RE = re.compile(r"\b(?:CVE-\d{4}-\d{4,}|GHSA(?:-[23456789cfghjmpqrvwx]{4}){3})\b", re.IGNORECASE)

ECOSYSTEM_MANIFESTS = {
    "npm": "package.json",
    "pypi": "requirements.txt",
    "pip": "requirements.txt",
    "go": "go.mod",
    "maven": "pom.xml",
    "rubygems": "Gemfile",
    "cargo": "Cargo.toml",
    "crates.io": "Cargo.toml",
    "nuget": "packages.config",
    "composer": "composer.json",
}


class UnsupportedFormat(ValueError):
    pass


def _cwes(*values: Any) -> list[str]:
    found: list[str] = []
    for v in values:
        for item in v if isinstance(v, list) else [v]:
            if item is None:
                continue
            for m in CWE_RE.findall(str(item)):
                cwe = m.upper()
                if cwe not in found:
                    found.append(cwe)
    return found


def _advisories(*values: Any) -> list[str]:
    found: list[str] = []
    for v in values:
        for item in v if isinstance(v, list) else [v]:
            if item is None:
                continue
            for m in ADVISORY_RE.findall(str(item)):
                adv = m.upper() if m.upper().startswith("CVE") else m
                if adv not in found:
                    found.append(adv)
    return found


def _rel(path: str | None) -> str | None:
    if not path:
        return None
    path = re.sub(r"^file://", "", str(path))
    path = path.replace("\\", "/")
    while path.startswith("./"):
        path = path[2:]
    return path


def _category_for(text: str, default: Category = Category.sast) -> Category:
    t = text.lower()
    if re.search(
        r"secret|hard-?coded[-_ ]?(password|credential|key|token)|api[-_ ]?key|private[-_ ]key|gitleaks"
        r"|leaked[-_ ]credential",
        t,
    ):
        return Category.secrets
    if re.search(r"terraform|cloudformation|kubernetes|k8s|helm|dockerfile|iac|checkov|tfsec|kics", t):
        return Category.iac
    if re.search(r"\bcve-|\bghsa-|dependency|vulnerable package|sca\b", t):
        return Category.sca
    return default


# --------------------------------------------------------------------------- SARIF


def parse_sarif(doc: dict[str, Any]) -> list[Finding]:
    out: list[Finding] = []
    for run in doc.get("runs") or []:
        driver = (run.get("tool") or {}).get("driver") or {}
        tool = driver.get("name") or "sarif"
        rules = {r.get("id"): r for r in driver.get("rules") or [] if isinstance(r, dict)}
        rules_by_index = driver.get("rules") or []
        for result in run.get("results") or []:
            rule_id = result.get("ruleId") or (result.get("rule") or {}).get("id") or "unknown"
            rule = rules.get(rule_id)
            if rule is None and isinstance(result.get("ruleIndex"), int) and result["ruleIndex"] < len(rules_by_index):
                rule = rules_by_index[result["ruleIndex"]]
            rule = rule or {}
            props = {**(rule.get("properties") or {}), **(result.get("properties") or {})}
            tags = props.get("tags") or []
            loc = ((result.get("locations") or [{}])[0] or {}).get("physicalLocation") or {}
            region = loc.get("region") or {}
            path = _rel((loc.get("artifactLocation") or {}).get("uri"))
            snippet = (region.get("snippet") or {}).get("text")
            message = (result.get("message") or {}).get("text") or ""
            title = (rule.get("shortDescription") or {}).get("text") or rule.get("name") or message[:120] or rule_id
            level = result.get("level") or (rule.get("defaultConfiguration") or {}).get("level")
            score = props.get("security-severity") or props.get("security_severity")
            text = " ".join([tool, rule_id, title, " ".join(map(str, tags)), str(props.get("category", ""))])
            category = _category_for(text)
            explicit = str(props.get("category", "")).lower()
            if explicit in Category.__members__:
                category = Category(explicit)
            pkg = None
            if category is Category.sca and props.get("packageName"):
                pkg = Package(name=props["packageName"], version=props.get("packageVersion"))
            out.append(
                Finding(
                    tool=tool,
                    rule_id=rule_id,
                    title=title,
                    message=message,
                    severity=severity_from(props.get("severity") or level, score),
                    category=category,
                    cwe=_cwes(props.get("cwe"), tags, rule.get("relationships")),
                    advisories=_advisories(rule_id, message, tags),
                    location=Location(
                        path=path or "",
                        start_line=region.get("startLine"),
                        end_line=region.get("endLine") or region.get("startLine"),
                        snippet=redact_text(snippet) if snippet else None,
                    )
                    if path
                    else None,
                    package=pkg,
                    help_uri=rule.get("helpUri"),
                    source_format="sarif",
                    raw=redact(result),
                )
            )
    return out


# --------------------------------------------------------------------------- Semgrep JSON


def parse_semgrep(doc: dict[str, Any]) -> list[Finding]:
    out = []
    for r in doc.get("results") or []:
        extra = r.get("extra") or {}
        meta = extra.get("metadata") or {}
        rule_id = r.get("check_id") or "semgrep"
        msg = extra.get("message") or ""
        out.append(
            Finding(
                tool="semgrep",
                rule_id=rule_id,
                title=msg.split("\n")[0][:160] or rule_id,
                message=msg,
                severity=severity_from(meta.get("impact") or extra.get("severity")),
                category=_category_for(" ".join([rule_id, str(meta.get("category", ""))])),
                cwe=_cwes(meta.get("cwe")),
                advisories=_advisories(meta.get("references")),
                location=Location(
                    path=_rel(r.get("path")) or "",
                    start_line=(r.get("start") or {}).get("line"),
                    end_line=(r.get("end") or {}).get("line"),
                    snippet=redact_text(extra["lines"]) if extra.get("lines") else None,
                ),
                help_uri=meta.get("source"),
                source_format="semgrep-json",
                raw=redact(r),
            )
        )
    return out


# --------------------------------------------------------------------------- Snyk Open Source


def parse_snyk(doc: Any) -> list[Finding]:
    projects = doc if isinstance(doc, list) else [doc]
    out = []
    for project in projects:
        manifest = project.get("displayTargetFile") or project.get("targetFile")
        eco = project.get("packageManager")
        for v in project.get("vulnerabilities") or []:
            ids = v.get("identifiers") or {}
            fixed = [str(x) for x in v.get("fixedIn") or []]
            out.append(
                Finding(
                    tool="snyk",
                    rule_id=v.get("id") or "snyk",
                    title=v.get("title") or v.get("id") or "Vulnerable dependency",
                    message=(v.get("description") or "")[:2000],
                    severity=severity_from(v.get("severity"), v.get("cvssScore")),
                    category=Category.sca,
                    cwe=_cwes(ids.get("CWE")),
                    advisories=_advisories(ids.get("CVE"), ids.get("GHSA")) or [v.get("id")],
                    location=Location(path=_rel(manifest) or manifest) if manifest else None,
                    package=Package(
                        name=v.get("packageName") or v.get("moduleName") or v.get("name"),
                        version=v.get("version"),
                        ecosystem=eco,
                        fixed_versions=fixed,
                        manifest=_rel(manifest),
                    ),
                    source_format="snyk-json",
                    raw=redact({k: v.get(k) for k in ("id", "from", "upgradePath", "isUpgradable", "isPatchable")}),
                )
            )
    return out


# --------------------------------------------------------------------------- Trivy


def parse_trivy(doc: dict[str, Any]) -> list[Finding]:
    out = []
    for res in doc.get("Results") or []:
        target = _rel(res.get("Target"))
        for v in res.get("Vulnerabilities") or []:
            fixed = [x.strip() for x in str(v.get("FixedVersion") or "").split(",") if x.strip()]
            out.append(
                Finding(
                    tool="trivy",
                    rule_id=v.get("VulnerabilityID") or "trivy-vuln",
                    title=v.get("Title") or v.get("VulnerabilityID") or "Vulnerable package",
                    message=(v.get("Description") or "")[:2000],
                    severity=severity_from(v.get("Severity")),
                    category=Category.container if res.get("Class") == "os-pkgs" else Category.sca,
                    cwe=_cwes(v.get("CweIDs")),
                    advisories=_advisories(v.get("VulnerabilityID")) or [v.get("VulnerabilityID")],
                    location=Location(path=target) if target else None,
                    package=Package(
                        name=v.get("PkgName"),
                        version=v.get("InstalledVersion"),
                        ecosystem=res.get("Type"),
                        fixed_versions=fixed,
                        manifest=target,
                    ),
                    help_uri=v.get("PrimaryURL"),
                    source_format="trivy-json",
                    raw=redact(
                        {k: v.get(k) for k in ("VulnerabilityID", "PkgName", "InstalledVersion", "FixedVersion")}
                    ),
                )
            )
        for m in res.get("Misconfigurations") or []:
            cause = m.get("CauseMetadata") or {}
            out.append(
                Finding(
                    tool="trivy",
                    rule_id=m.get("ID") or m.get("AVDID") or "trivy-misconfig",
                    title=m.get("Title") or "Misconfiguration",
                    message=m.get("Message") or m.get("Description") or "",
                    severity=severity_from(m.get("Severity")),
                    category=Category.iac,
                    location=Location(
                        path=target or "", start_line=cause.get("StartLine"), end_line=cause.get("EndLine")
                    ),
                    help_uri=m.get("PrimaryURL"),
                    source_format="trivy-json",
                    raw=redact(m),
                )
            )
        for s in res.get("Secrets") or []:
            out.append(
                Finding(
                    tool="trivy",
                    rule_id=s.get("RuleID") or "trivy-secret",
                    title=s.get("Title") or "Exposed secret",
                    severity=severity_from(s.get("Severity")),
                    category=Category.secrets,
                    location=Location(path=target or "", start_line=s.get("StartLine"), end_line=s.get("EndLine")),
                    source_format="trivy-json",
                    raw={"RuleID": s.get("RuleID")},  # never keep the secret itself
                )
            )
    return out


# --------------------------------------------------------------------------- OSV-Scanner


def _osv_fixed(vuln: dict[str, Any], name: str) -> list[str]:
    fixed: list[str] = []
    for aff in vuln.get("affected") or []:
        if (aff.get("package") or {}).get("name") not in (None, name):
            continue
        for rng in aff.get("ranges") or []:
            for ev in rng.get("events") or []:
                if ev.get("fixed") and ev["fixed"] not in fixed:
                    fixed.append(ev["fixed"])
    return fixed


def parse_osv(doc: dict[str, Any]) -> list[Finding]:
    out = []
    for res in doc.get("results") or []:
        manifest = _rel((res.get("source") or {}).get("path"))
        for p in res.get("packages") or []:
            pkg = p.get("package") or {}
            groups = p.get("groups") or []
            for v in p.get("vulnerabilities") or []:
                score = None
                for g in groups:
                    if v.get("id") in (g.get("ids") or []):
                        score = g.get("max_severity")
                sev_word = (v.get("database_specific") or {}).get("severity")
                out.append(
                    Finding(
                        tool="osv-scanner",
                        rule_id=v.get("id") or "osv",
                        title=v.get("summary") or v.get("id") or "Vulnerable package",
                        message=(v.get("details") or "")[:2000],
                        severity=severity_from(sev_word, score),
                        category=Category.sca,
                        cwe=_cwes((v.get("database_specific") or {}).get("cwe_ids")),
                        advisories=_advisories(v.get("id"), v.get("aliases")) or [v.get("id")],
                        location=Location(path=manifest) if manifest else None,
                        package=Package(
                            name=pkg.get("name") or "unknown",
                            version=pkg.get("version"),
                            ecosystem=(pkg.get("ecosystem") or "").lower() or None,
                            fixed_versions=_osv_fixed(v, pkg.get("name") or ""),
                            manifest=manifest,
                        ),
                        source_format="osv-json",
                        raw={"id": v.get("id"), "aliases": v.get("aliases")},
                    )
                )
    return out


# --------------------------------------------------------------------------- Gitleaks


def parse_gitleaks(doc: list[dict[str, Any]]) -> list[Finding]:
    return [
        Finding(
            tool="gitleaks",
            rule_id=g.get("RuleID") or "gitleaks",
            title=g.get("Description") or "Hardcoded secret",
            severity=Severity.high,
            category=Category.secrets,
            location=Location(path=_rel(g.get("File")) or "", start_line=g.get("StartLine"), end_line=g.get("EndLine")),
            source_format="gitleaks-json",
            raw={"RuleID": g.get("RuleID"), "Fingerprint": g.get("Fingerprint"), "Commit": g.get("Commit")},
        )
        for g in doc
    ]


# --------------------------------------------------------------------------- GitHub


def parse_github_code_scanning(doc: list[dict[str, Any]]) -> list[Finding]:
    out = []
    for a in doc:
        rule = a.get("rule") or {}
        inst = a.get("most_recent_instance") or {}
        loc = inst.get("location") or {}
        tool = (a.get("tool") or {}).get("name") or "github-code-scanning"
        out.append(
            Finding(
                tool=tool,
                rule_id=rule.get("id") or "unknown",
                title=rule.get("description") or (inst.get("message") or {}).get("text") or "Code scanning alert",
                message=(inst.get("message") or {}).get("text") or "",
                severity=severity_from(rule.get("security_severity_level") or rule.get("severity")),
                category=_category_for(" ".join([tool, rule.get("id") or "", " ".join(rule.get("tags") or [])])),
                cwe=_cwes(rule.get("tags")),
                location=Location(
                    path=_rel(loc.get("path")) or "", start_line=loc.get("start_line"), end_line=loc.get("end_line")
                ),
                help_uri=a.get("html_url"),
                source_format="github-code-scanning",
                raw=redact({"number": a.get("number"), "state": a.get("state"), "commit_sha": inst.get("commit_sha")}),
            )
        )
    return out


def parse_dependabot(doc: list[dict[str, Any]]) -> list[Finding]:
    out = []
    for a in doc:
        adv = a.get("security_advisory") or {}
        vuln = a.get("security_vulnerability") or {}
        pkg = vuln.get("package") or {}
        dep = a.get("dependency") or {}
        patched = (vuln.get("first_patched_version") or {}).get("identifier")
        manifest = _rel(dep.get("manifest_path"))
        out.append(
            Finding(
                tool="dependabot",
                rule_id=adv.get("ghsa_id") or "dependabot",
                title=adv.get("summary") or "Vulnerable dependency",
                message=(adv.get("description") or "")[:2000],
                severity=severity_from(adv.get("severity"), (adv.get("cvss") or {}).get("score")),
                category=Category.sca,
                cwe=_cwes([c.get("cwe_id") for c in adv.get("cwes") or []]),
                advisories=_advisories(adv.get("ghsa_id"), adv.get("cve_id")),
                location=Location(path=manifest) if manifest else None,
                package=Package(
                    name=pkg.get("name") or "unknown",
                    ecosystem=pkg.get("ecosystem"),
                    version=None,
                    fixed_versions=[patched] if patched else [],
                    manifest=manifest,
                ),
                help_uri=a.get("html_url"),
                source_format="github-dependabot",
                raw={"number": a.get("number"), "vulnerable_version_range": vuln.get("vulnerable_version_range")},
            )
        )
    return out


# --------------------------------------------------------------------------- OpenFix native


def parse_openfix(doc: dict[str, Any]) -> list[Finding]:
    return [Finding.model_validate({**f, "source_format": "openfix"}) for f in doc.get("findings") or []]


# --------------------------------------------------------------------------- dispatch


def detect(doc: Any) -> tuple[str, Callable[[Any], list[Finding]]]:
    if isinstance(doc, dict):
        if str(doc.get("openfix", "")).startswith("findings/"):
            return "openfix", parse_openfix
        if isinstance(doc.get("runs"), list) and ("version" in doc or "$schema" in doc):
            return "sarif", parse_sarif
        if (
            isinstance(doc.get("results"), list)
            and (not doc["results"] or "check_id" in (doc["results"][0] or {}))
            and "errors" in doc
        ):
            return "semgrep-json", parse_semgrep
        if isinstance(doc.get("results"), list) and doc["results"] and "packages" in doc["results"][0]:
            return "osv-json", parse_osv
        if isinstance(doc.get("Results"), list) or doc.get("ArtifactName"):
            return "trivy-json", parse_trivy
        if isinstance(doc.get("vulnerabilities"), list):
            return "snyk-json", parse_snyk
    if isinstance(doc, list):
        if not doc:
            return "empty", lambda _d: []
        first = doc[0] if isinstance(doc[0], dict) else {}
        if "vulnerabilities" in first and ("packageManager" in first or "projectName" in first):
            return "snyk-json", parse_snyk
        if "RuleID" in first and ("File" in first or "Secret" in first):
            return "gitleaks-json", parse_gitleaks
        if "most_recent_instance" in first:
            return "github-code-scanning", parse_github_code_scanning
        if "security_advisory" in first and "security_vulnerability" in first:
            return "github-dependabot", parse_dependabot
    raise UnsupportedFormat(
        "Unrecognised findings format. Supported: SARIF 2.1, Semgrep JSON, Snyk JSON, Trivy JSON, "
        "OSV-Scanner JSON, Gitleaks JSON, GitHub code-scanning/Dependabot alerts, OpenFix findings JSON."
    )


SECRET_CWES = {"CWE-798", "CWE-259", "CWE-321", "CWE-522"}


def load_document(doc: Any) -> list[Finding]:
    _, parser = detect(doc)
    findings = parser(doc)
    for f in findings:
        if f.category is Category.sast and SECRET_CWES & set(f.cwe):
            f.category = Category.secrets
    return findings


def load_file(path: str | Path) -> list[Finding]:
    p = Path(path)
    size = p.stat().st_size
    if size > MAX_INPUT_BYTES:
        raise ValueError(f"{p} is {size} bytes; the limit is {MAX_INPUT_BYTES}")
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{p} is not valid JSON ({exc.msg} at line {exc.lineno})") from None
    return load_document(doc)


def load_files(paths: Iterable[str | Path]) -> list[Finding]:
    """Load and de-duplicate findings from several reports (same fingerprint -> one finding)."""
    seen: dict[str, Finding] = {}
    for path in paths:
        for f in load_file(path):
            if f.id not in seen or f.severity.rank > seen[f.id].severity.rank:
                seen[f.id] = f
    return list(seen.values())
