import json
from pathlib import Path

import pytest

from openfix.findings import Category, Severity
from openfix.ingest import UnsupportedFormat, detect, load_document, load_file

EXAMPLE_SARIF = Path(__file__).parent.parent / "examples" / "vulnerable-app" / "findings" / "semgrep.sarif"


def test_sarif_example_report():
    findings = load_file(EXAMPLE_SARIF)
    assert len(findings) == 10
    pt = next(f for f in findings if "path-traversal" in f.rule_id)
    assert pt.tool.lower() == "semgrep oss"
    assert pt.location.path == "src/files.js" and pt.location.start_line == 11
    assert pt.severity is Severity.high  # security-severity 7.5
    assert pt.cwe == ["CWE-22"]
    secret = next(f for f in findings if "hardcoded-api-token" in f.rule_id)
    assert secret.category is Category.secrets


def test_sarif_rule_index_cwe_and_security_severity():
    doc = {
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "CodeQL",
                        "rules": [
                            {
                                "id": "js/sql-injection",
                                "shortDescription": {"text": "Database query built from user input"},
                                "properties": {
                                    "tags": ["security", "external/cwe/cwe-089"],
                                    "security-severity": "9.8",
                                },
                            }
                        ],
                    }
                },
                "results": [
                    {
                        "ruleIndex": 0,
                        "ruleId": "js/sql-injection",
                        "message": {"text": "This query depends on x"},
                        "locations": [
                            {
                                "physicalLocation": {
                                    "artifactLocation": {"uri": "./src/db.js"},
                                    "region": {"startLine": 12},
                                }
                            }
                        ],
                    }
                ],
            }
        ],
    }
    [f] = load_document(doc)
    assert f.cwe == ["CWE-089"]
    assert f.severity is Severity.critical
    assert f.location.path == "src/db.js"


def test_semgrep_json():
    doc = {
        "errors": [],
        "results": [
            {
                "check_id": "python.lang.security.audit.eval-detected",
                "path": "app.py",
                "start": {"line": 3},
                "end": {"line": 3},
                "extra": {
                    "message": "Detected eval",
                    "severity": "ERROR",
                    "metadata": {"cwe": ["CWE-95: Eval Injection"], "category": "security"},
                    "lines": "eval(x)",
                },
            }
        ],
    }
    [f] = load_document(doc)
    assert f.tool == "semgrep" and f.cwe == ["CWE-95"] and f.severity is Severity.high
    assert detect(doc)[0] == "semgrep-json"


def test_snyk_open_source():
    doc = {
        "packageManager": "npm",
        "displayTargetFile": "package.json",
        "vulnerabilities": [
            {
                "id": "SNYK-JS-LODASH-567746",
                "title": "Prototype Pollution",
                "severity": "high",
                "packageName": "lodash",
                "version": "4.17.15",
                "fixedIn": ["4.17.19"],
                "identifiers": {"CVE": ["CVE-2020-8203"], "CWE": ["CWE-1321"]},
            }
        ],
    }
    [f] = load_document(doc)
    assert f.category is Category.sca
    assert f.package.name == "lodash" and f.package.fixed_versions == ["4.17.19"]
    assert f.advisories == ["CVE-2020-8203"]


def test_trivy_vulns_misconfig_and_secrets_never_keep_secret():
    doc = {
        "ArtifactName": ".",
        "Results": [
            {
                "Target": "package-lock.json",
                "Class": "lang-pkgs",
                "Type": "npm",
                "Vulnerabilities": [
                    {
                        "VulnerabilityID": "CVE-2021-23337",
                        "PkgName": "lodash",
                        "InstalledVersion": "4.17.15",
                        "FixedVersion": "4.17.21",
                        "Severity": "HIGH",
                        "Title": "Command injection",
                    }
                ],
            },
            {
                "Target": "main.tf",
                "Class": "config",
                "Misconfigurations": [
                    {"ID": "AVD-AWS-0086", "Title": "S3 public", "Severity": "HIGH", "CauseMetadata": {"StartLine": 4}}
                ],
            },
            {
                "Target": "config.js",
                "Class": "secret",
                "Secrets": [
                    {
                        "RuleID": "aws-access-key-id",
                        "Title": "AWS key",
                        "Severity": "CRITICAL",
                        "StartLine": 2,
                        "Match": "AKIAABCDEFGHIJKLMNOP",
                    }
                ],
            },
        ],
    }
    findings = load_document(doc)
    cats = sorted(f.category.value for f in findings)
    assert cats == ["iac", "sca", "secrets"]
    assert "AKIA" not in json.dumps([f.model_dump(mode="json") for f in findings])


def test_osv_scanner():
    doc = {
        "results": [
            {
                "source": {"path": "requirements.txt", "type": "lockfile"},
                "packages": [
                    {
                        "package": {"name": "jinja2", "version": "2.10", "ecosystem": "PyPI"},
                        "groups": [{"ids": ["GHSA-462w-v97r-4m45"], "max_severity": "7.5"}],
                        "vulnerabilities": [
                            {
                                "id": "GHSA-462w-v97r-4m45",
                                "aliases": ["CVE-2019-10906"],
                                "summary": "Sandbox escape",
                                "affected": [
                                    {
                                        "package": {"name": "jinja2"},
                                        "ranges": [{"events": [{"introduced": "0"}, {"fixed": "2.10.1"}]}],
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }
        ]
    }
    [f] = load_document(doc)
    assert f.package.fixed_versions == ["2.10.1"] and f.severity is Severity.high
    assert "CVE-2019-10906" in f.advisories


def test_gitleaks_drops_secret_material():
    doc = [
        {
            "RuleID": "github-pat",
            "Description": "GitHub PAT",
            "File": "src/a.js",
            "StartLine": 3,
            "Secret": "ghp_" + "x" * 36,
            "Match": "token = ghp_" + "x" * 36,
            "Fingerprint": "abc",
        }
    ]
    [f] = load_document(doc)
    assert f.category is Category.secrets
    assert "ghp_" not in json.dumps(f.model_dump(mode="json"))


def test_github_alerts_and_dependabot():
    cs = [
        {
            "number": 4,
            "rule": {
                "id": "py/path-injection",
                "security_severity_level": "high",
                "description": "Uncontrolled data used in path expression",
                "tags": ["security", "external/cwe/cwe-022"],
            },
            "tool": {"name": "CodeQL"},
            "most_recent_instance": {"location": {"path": "app/files.py", "start_line": 9}, "commit_sha": "abc"},
        }
    ]
    [f] = load_document(cs)
    assert f.tool == "CodeQL" and f.cwe == ["CWE-022"]
    dep = [
        {
            "number": 1,
            "dependency": {"manifest_path": "package.json"},
            "security_advisory": {
                "ghsa_id": "GHSA-p6mc-m468-83gw",
                "cve_id": "CVE-2020-8203",
                "severity": "high",
                "summary": "Prototype pollution",
            },
            "security_vulnerability": {
                "package": {"ecosystem": "npm", "name": "lodash"},
                "first_patched_version": {"identifier": "4.17.19"},
            },
        }
    ]
    [d] = load_document(dep)
    assert d.package.fixed_versions == ["4.17.19"] and d.category is Category.sca


def test_unknown_format_is_rejected():
    with pytest.raises(UnsupportedFormat):
        load_document({"hello": "world"})


def test_fingerprint_is_stable():
    a = load_file(EXAMPLE_SARIF)
    b = load_file(EXAMPLE_SARIF)
    assert [f.id for f in a] == [f.id for f in b]
