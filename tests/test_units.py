import json

from openfix.deps import choose_fixed_version, try_bump
from openfix.findings import Category, Finding, Location, Package, Severity
from openfix.policy import Action, Policy, glob_match
from openfix.redact import redact
from openfix.sarif_out import to_sarif
from openfix.scanners import line_map, matches


def finding(**kw):
    base = dict(tool="semgrep", rule_id="x.path-traversal", title="t", location=Location(path="src/a.js", start_line=5))
    base.update(kw)
    return Finding(**base)


def test_default_policy_decisions():
    p = Policy()
    assert p.decide(finding()).action is Action.autofix
    assert p.decide(finding(category=Category.secrets)).action is Action.skip
    assert p.decide(finding(location=Location(path="src/auth/login.js", start_line=1))).action is Action.propose
    assert p.decide(finding(category=Category.iac)).action is Action.propose
    assert p.decide(finding(severity=Severity.info)).action is Action.skip


def test_policy_rule_and_local_only():
    p = Policy.model_validate(
        {
            "rules": [
                {"match": {"cwe": ["CWE-89"]}, "action": "propose", "name": "sqli to humans"},
                {"match": {}, "action": "autofix"},
            ],
            "models": {"local_only_paths": ["services/payments/**"]},
        }
    )
    d = p.decide(finding(cwe=["CWE-89"]))
    assert d.action is Action.propose and d.rule == "sqli to humans"
    assert p.decide(finding(location=Location(path="services/payments/x.py"))).local_only


def test_glob():
    assert glob_match("**/auth/**", "src/auth/tokens.js")
    assert glob_match("**/auth/**", "auth/tokens.js")
    assert glob_match(".github/workflows/**", ".github/workflows/ci.yml")
    assert glob_match("*.lock", "deep/dir/yarn.lock")
    assert not glob_match("src/*.js", "src/a/b.js")


def test_choose_fixed_version():
    assert choose_fixed_version("4.17.15", ["4.17.19", "4.17.21"]) == "4.17.19"
    assert choose_fixed_version("1.2.0", ["2.0.1", "1.4.3"]) == "1.4.3"
    assert choose_fixed_version("3.0.0", ["2.9.9"]) is None
    assert choose_fixed_version(None, ["1.0.1", "1.0.0"]) == "1.0.0"


def test_npm_bump_preserves_formatting(tmp_path):
    (tmp_path / "package.json").write_text('{\n  "dependencies": {\n    "lodash": "^4.17.15",\n    "x": "1"\n  }\n}\n')
    f = Finding(
        tool="snyk",
        rule_id="SNYK-1",
        title="pp",
        category=Category.sca,
        package=Package(name="lodash", version="4.17.15", fixed_versions=["4.17.21"], manifest="package.json"),
    )
    fix = try_bump(tmp_path, f)
    assert fix and fix.new == "^4.17.21"
    assert (tmp_path / "package.json").read_text() == (
        '{\n  "dependencies": {\n    "lodash": "^4.17.21",\n    "x": "1"\n  }\n}\n'
    )


def test_pip_bump(tmp_path):
    (tmp_path / "requirements.txt").write_text("flask==2.0.1\nJinja2==2.10  # templating\n")
    f = Finding(
        tool="osv",
        rule_id="GHSA",
        title="x",
        category=Category.sca,
        package=Package(name="jinja2", version="2.10", fixed_versions=["2.10.1"], manifest="requirements.txt"),
    )
    assert try_bump(tmp_path, f)
    assert "Jinja2==2.10.1  # templating" in (tmp_path / "requirements.txt").read_text()


def test_line_map_follows_edits():
    before = "a\nb\nc\nd\n"
    after = "a\nNEW1\nNEW2\nb\nc\nd\n"
    m = line_map(before, after)
    assert m[1] == 1 and m[2] == 4 and m[4] == 6


def test_matches_tolerates_line_shift():
    target = finding()
    moved = finding(location=Location(path="src/a.js", start_line=7))
    assert matches(target, moved, {5: 7})
    assert not matches(target, finding(location=Location(path="src/b.js", start_line=5)))
    # Semgrep prefixes rule ids with the config path; the dotted tail still matches.
    assert matches(target, finding(rule_id="javascript.lang.security.audit.path-traversal"), None)


def test_redact():
    out = redact({"api_key": "abc", "note": "token sk-ant-" + "a" * 30, "nested": ["AKIAABCDEFGHIJKLMNOP"]})
    s = json.dumps(out)
    assert "abc" not in s and "sk-ant" not in s and "AKIA" not in s


def test_sarif_fixes_output():
    f = finding()
    doc = to_sarif(
        [
            {
                "finding": f,
                "status": "verified",
                "summary": "s",
                "files": {"src/a.js": ("one\ntwo\n", "one\nTWO\nthree\n")},
            }
        ]
    )
    [res] = doc["runs"][0]["results"]
    [fix] = res["fixes"]
    [change] = fix["artifactChanges"]
    assert change["replacements"][0]["deletedRegion"]["startLine"] == 2
    assert change["replacements"][0]["insertedContent"]["text"] == "TWO\nthree\n"


def test_untrusted_finding_ids_are_replaced():
    for bad in ("../../etc", "a/b", "", "x" * 100, ".hidden"):
        f = Finding(id=bad, tool="t", rule_id="r", title="x")
        assert f.id.startswith("of-")
    assert Finding(id="CUSTOM-1.2_x", tool="t", rule_id="r", title="x").id == "CUSTOM-1.2_x"


def test_scanner_can_be_chosen_per_tool():
    from openfix.engine import scanner_spec
    from openfix.policy import Command

    p = Policy.model_validate(
        {"verify": {"scanner": {"semgrep": {"command": "semgrep --config r.yml {output}"}, "snyk-code": "snyk-code"}}}
    )
    semgrep = scanner_spec(p.verify.scanner, finding(tool="Semgrep OSS"))
    assert isinstance(semgrep, Command) and semgrep.command.startswith("semgrep --config r.yml")
    assert scanner_spec(p.verify.scanner, finding(tool="SnykCode")) == "snyk-code"
    assert scanner_spec(p.verify.scanner, finding(tool="trivy")) is None  # falls back to the tool's preset
    single = Policy.model_validate({"verify": {"scanner": {"command": "x {output}"}}})
    assert isinstance(single.verify.scanner, Command)


def test_scripted_provider_picks_steps_per_finding():
    from openfix.providers.scripted import ScriptedProvider

    p = ScriptedProvider("demo", steps={"rule-a": [{"tool": "submit", "args": {"summary": "a"}}], "rule-b": []})
    turn = p.start("sys", []).send(user='{"rule_id": "rule-a"}')
    assert turn.tool_calls[0].name == "submit" and turn.tool_calls[0].arguments == {"summary": "a"}
    assert not p.start("sys", []).send(user='{"rule_id": "rule-b"}').tool_calls
    assert not p.start("sys", []).send(user='{"rule_id": "other"}').tool_calls


def test_console_lines_are_plain_without_a_terminal(monkeypatch):
    from openfix.console import finding_line, result_line

    monkeypatch.delenv("FORCE_COLOR", raising=False)
    line = finding_line(finding(tool="SnykCode", title="Command Injection", severity=Severity.high))
    assert line == "→ Snyk Code  high    Command Injection  src/a.js:5"
    assert "x.path-traversal" in finding_line(finding(tool="Semgrep OSS", title="Semgrep Finding: x.path-traversal"))
    ok = result_line("verified", "", [("rescan", "passed"), ("regression_test", "passed")])
    assert ok == "  ✔ rescan   ✔ regression test   → verified"
    pr = result_line("verified", "", [("tests", "passed")], "https://github.com/o/r/pull/1")
    assert pr == "  ✔ tests   → verified\n    draft PR https://github.com/o/r/pull/1"
    bad = result_line("failed", "rescan: failed", [("rescan", "failed"), ("tests", "not_run")])
    assert bad == "  ✘ rescan   · tests   → failed\n    rescan: failed"


def test_open_pull_request_twice_reuses_the_branch(tmp_path, monkeypatch):
    """A rerun in the same clone must not fail because the PR branch already exists locally."""
    import subprocess

    from openfix import github

    def sh(*args, cwd):
        subprocess.run(args, cwd=cwd, check=True, capture_output=True)

    remote, repo = tmp_path / "remote.git", tmp_path / "repo"
    sh("git", "init", "-q", "--bare", str(remote), cwd=tmp_path)
    sh("git", "init", "-q", "-b", "main", str(repo), cwd=tmp_path)
    (repo / "a.txt").write_text("a\n")
    sh("git", "add", "-A", cwd=repo)
    sh("git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "--no-verify", "-qm", "init", cwd=repo)
    sh("git", "remote", "add", "origin", str(remote), cwd=repo)

    class FakeResponse:
        status_code, text = 201, ""

        def json(self):
            return {"html_url": "https://github.com/o/r/pull/1", "number": 1}

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def post(self, *a, **kw):
            return FakeResponse()

    monkeypatch.setenv("GITHUB_TOKEN", "test")
    monkeypatch.setenv("GITHUB_REPOSITORY", "o/r")
    monkeypatch.setattr(github, "_client", lambda token: FakeClient())
    for n in (1, 2):
        work = tmp_path / f"wt{n}"
        sh("git", "worktree", "add", "-q", "--detach", str(work), "main", cwd=repo)
        (work / "a.txt").write_text(f"fix {n}\n")
        url = github.open_pull_request(
            work, branch="openfix/x", title="t", body="b", commit_message="m", labels=[], draft=True, base_branch="main"
        )
        assert url == "https://github.com/o/r/pull/1"
        sh("git", "worktree", "remove", "--force", str(work), cwd=repo)
