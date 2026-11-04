"""End-to-end: a real git repo, a real (tiny) scanner, real tests, and a scripted model."""

import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from openfix.engine import Engine, Options
from openfix.ingest import load_document
from openfix.policy import Policy
from openfix.providers.scripted import ScriptedProvider
from openfix.receipt import verify_receipt

SCANNER = textwrap.dedent("""
    import json, pathlib, sys
    out = sys.argv[1]
    results = []
    for p in sorted(pathlib.Path(".").rglob("*.py")):
        if "test" in p.name:
            continue
        for n, line in enumerate(p.read_text().splitlines(), 1):
            if "open(os.path.join(BASE_DIR," in line:
                results.append({"ruleId": "toy.path-traversal", "level": "error",
                    "message": {"text": "user path joined onto BASE_DIR"},
                    "locations": [{"physicalLocation": {"artifactLocation": {"uri": p.as_posix()},
                                                        "region": {"startLine": n}}}]})
    pathlib.Path(out).parent.mkdir(parents=True, exist_ok=True)
    json.dump({"version": "2.1.0", "runs": [{"tool": {"driver": {"name": "toyscan"}}, "results": results}]},
              open(out, "w"))
""")

APP = textwrap.dedent("""
    import os

    BASE_DIR = os.path.join(os.path.dirname(__file__), "data")


    def read_user_file(user_path):
        return open(os.path.join(BASE_DIR, user_path)).read()
""")

FIXED_BODY = """def read_user_file(user_path):
    base = os.path.realpath(BASE_DIR)
    target = os.path.realpath(os.path.join(base, user_path))
    if os.path.commonpath([base, target]) != base:
        raise PermissionError("path escapes the data directory")
    with open(target) as fh:
        return fh.read()"""

REGRESSION_TEST = textwrap.dedent("""
    import pytest
    from app import read_user_file


    def test_rejects_traversal():
        with pytest.raises(PermissionError):
            read_user_file("../secret.txt")
""")


def sh(cwd, *args):
    subprocess.run(args, cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    (r / "data").mkdir(parents=True)
    (r / "data" / "hello.txt").write_text("hello\n")
    (r / "secret.txt").write_text("top secret\n")
    (r / "app.py").write_text(APP)
    (r / "test_app.py").write_text(
        "from app import read_user_file\n\n\ndef test_reads():\n    assert read_user_file('hello.txt') == 'hello\\n'\n"
    )
    sh(r, "git", "init", "-q", "-b", "main")
    sh(r, "git", "add", "-A")
    sh(
        r,
        "git",
        "-c",
        "user.name=t",
        "-c",
        "user.email=t@t",
        "-c",
        "commit.gpgsign=false",
        "-c",
        "core.hooksPath=/dev/null",
        "commit",
        "--no-verify",
        "-qm",
        "init",
    )
    scanner = tmp_path / "toyscan.py"
    scanner.write_text(SCANNER)
    return r, scanner


def make_policy(scanner: Path, require):
    return Policy.model_validate(
        {
            "verify": {
                "require": require,
                "tests": {"command": f"{sys.executable} -m pytest -q -p no:cacheprovider"},
                "scanner": {"command": f"{sys.executable} {scanner} {{output}}"},
            },
            "sandbox": {"backend": "local"},
        }
    )


def the_finding(line=7):
    doc = {
        "version": "2.1.0",
        "runs": [
            {
                "tool": {"driver": {"name": "toyscan"}},
                "results": [
                    {
                        "ruleId": "toy.path-traversal",
                        "level": "error",
                        "message": {"text": "user path joined onto BASE_DIR"},
                        "locations": [
                            {"physicalLocation": {"artifactLocation": {"uri": "app.py"}, "region": {"startLine": line}}}
                        ],
                    }
                ],
            }
        ],
    }
    return load_document(doc)


def run_with_script(repo_dir, scanner, steps, require, tmp_path):
    policy = make_policy(scanner, require)
    engine = Engine(repo_dir, policy, Options(out=tmp_path / "out"), log=lambda _m: None)
    engine._providers[policy.models.author] = ScriptedProvider("script", steps)
    return engine, engine.run(the_finding())


def good_steps():
    return [
        {"tool": "read_file", "args": {"path": "app.py"}},
        {
            "tool": "edit_file",
            "args": {
                "path": "app.py",
                "old_text": "def read_user_file(user_path):\n    return open(os.path.join(BASE_DIR, user_path)).read()",
                "new_text": FIXED_BODY,
            },
        },
        {"tool": "write_file", "args": {"path": "test_traversal.py", "content": REGRESSION_TEST}},
        {"tool": "run_tests", "args": {}},
        {"tool": "rescan", "args": {}},
        {
            "tool": "submit",
            "args": {
                "summary": "Resolve the path and reject anything outside BASE_DIR.",
                "regression_test": "test_traversal.py",
                "confidence": "high",
            },
        },
    ]


def test_verified_fix_produces_valid_receipt(repo, tmp_path):
    repo_dir, scanner = repo
    engine, [o] = run_with_script(repo_dir, scanner, good_steps(), ["rescan", "tests", "regression_test"], tmp_path)
    by = {c.name: c.status for c in o.checks}
    assert o.status == "verified", (o.detail, [c.to_dict() for c in o.checks])
    assert by == {"rescan": "passed", "tests": "passed", "regression_test": "passed"}
    rows = verify_receipt(o.out_dir, repo_dir)
    assert all(ok for _, ok, _ in rows), rows
    receipt = json.loads((o.out_dir / "receipt.json").read_text())
    assert receipt["predicate"]["status"] == "verified"
    assert receipt["predicate"]["patch"]["files"][0]["path"] in ("app.py", "test_traversal.py")
    sarif = json.loads((engine.out / "openfix.sarif").read_text())
    assert sarif["runs"][0]["results"][0]["fixes"]
    # The user's working tree is untouched.
    assert "realpath" not in (repo_dir / "app.py").read_text()


def test_fix_that_does_not_remove_the_finding_fails(repo, tmp_path):
    repo_dir, scanner = repo
    steps = [
        {
            "tool": "edit_file",
            "args": {
                "path": "app.py",
                "old_text": "def read_user_file(user_path):",
                "new_text": "def read_user_file(user_path):  # sanitized",
            },
        },
        {"tool": "submit", "args": {"summary": "added a comment"}},
    ]
    _, [o] = run_with_script(repo_dir, scanner, steps, ["rescan", "tests"], tmp_path)
    assert o.status == "failed"
    assert {c.name: c.status for c in o.checks}["rescan"] == "failed"


def test_regression_test_that_passes_on_original_is_rejected(repo, tmp_path):
    repo_dir, scanner = repo
    steps = good_steps()
    steps[2] = {
        "tool": "write_file",
        "args": {"path": "test_traversal.py", "content": "def test_nothing():\n    assert True\n"},
    }
    _, [o] = run_with_script(repo_dir, scanner, steps, ["rescan", "tests", "regression_test"], tmp_path)
    assert {c.name: c.status for c in o.checks}["regression_test"] == "failed"
    assert o.status == "failed"


def test_protected_paths_are_refused(repo, tmp_path):
    repo_dir, scanner = repo
    steps = [
        {"tool": "write_file", "args": {"path": ".github/workflows/ci.yml", "content": "x"}},
        {"tool": "write_file", "args": {"path": "../outside.txt", "content": "x"}},
        {"tool": "give_up", "args": {"reason": "cannot"}},
    ]
    engine, [o] = run_with_script(repo_dir, scanner, steps, ["rescan"], tmp_path)
    log = json.loads((o.out_dir / "agent-log.json").read_text())["tools"]
    assert [t["ok"] for t in log] == [False, False, True]
    assert "protected" in log[0]["refused"] and "outside" in log[1]["refused"]
    assert o.status == "no_fix"
    assert not (tmp_path / "outside.txt").exists()


def test_stale_finding_is_not_sent_to_a_model(repo, tmp_path):
    repo_dir, scanner = repo
    (repo_dir / "app.py").write_text(APP.replace("open(os.path.join(BASE_DIR, user_path))", "open(user_path)"))
    sh(
        repo_dir,
        "git",
        "-c",
        "user.name=t",
        "-c",
        "user.email=t@t",
        "-c",
        "commit.gpgsign=false",
        "-c",
        "core.hooksPath=/dev/null",
        "commit",
        "--no-verify",
        "-qam",
        "change",
    )
    provider = ScriptedProvider("script", good_steps())
    policy = make_policy(scanner, ["rescan", "tests"])
    engine = Engine(repo_dir, policy, Options(out=tmp_path / "out"), log=lambda _m: None)
    engine._providers[policy.models.author] = provider
    [o] = engine.run(the_finding())
    assert o.status == "not_reproduced"
    assert provider.transcript == []  # no model call was made
