# OpenFix

**Fix security findings with any model. Every fix ships with proof.**

OpenFix takes findings from the scanners you already run (Semgrep, CodeQL, Snyk, Trivy, OSV-Scanner, Gitleaks,
GitHub code scanning, Dependabot, or anything that writes SARIF), decides what may be fixed under a policy you
control, has a model of your choice write a minimal patch in an isolated checkout, and then **verifies the patch
independently**. The model doesn't vouch for the fix; the checks do:

| Check | What it proves |
|---|---|
| **Rescan** | The original scanner reports the finding on the original code **and** no longer reports it on the patched code. |
| **Tests** | The project's own test suite still passes on the patched code (and is compared against the original code). |
| **Regression test** | The test the agent added **fails on the original code and passes with the fix**, so it actually exercises the vulnerability. |
| **Review** *(optional)* | A second model, ideally from a different provider, reviews the exact diff for bypasses and behavior changes. |

The result is a **fix receipt**: an [in-toto](https://in-toto.io) statement bound to the exact patch hash, with the
policy decision, the model and token usage, and the evidence for every check. You can sign it with Sigstore and
re-verify it later. When every required check passes, OpenFix can open a draft pull request. It never merges.

```
scanner report ─▶ normalize ─▶ policy ─▶ isolated worktree ─▶ agent (any model) ─▶ patch
                                 │                                                   │
                                 └─ skip / propose / autofix        rescan · tests · regression test · review
                                                                                     │
                                                         receipt.json + patch.diff + SARIF fixes[] ─▶ draft PR
```

## Why OpenFix

- **Any model.** Claude, OpenAI, Gemini, Grok, OpenRouter, Groq, DeepSeek, Mistral, Together, Fireworks, any
  OpenAI-compatible gateway, or a local model through Ollama, vLLM or LM Studio. Switch with `--model provider:model`.
- **Proof, not prose.** Verification is a separate step that doesn't trust the agent. Stale findings that the scanner
  can't reproduce are dropped *before* any model is called.
- **Policy as code.** One YAML file decides what is auto-fixed, what only gets a proposed patch, and what is never
  sent to a model. It also sets change-size limits, protected paths, budgets, and which code may only be seen by
  local models.
- **A small attack surface for the agent.** The model has no shell, no network and no git. It can read, search, edit,
  run the configured tests and re-run the scanner, and every write is checked against the policy. Tests run in a
  throwaway Docker container with no network by default.
- **Deterministic when possible.** A vulnerable direct dependency is bumped to the lowest fixed version without a
  model at all.
- **Fits your pipeline.** CLI, GitHub Action, SARIF in and SARIF out (with `fixes[]`), and JSON receipts.

## Quick start

```bash
pip install "openfix[all]"            # or: pipx install "openfix[all]"  /  uv tool install "openfix[all]"
export ANTHROPIC_API_KEY=...           # or OPENAI_API_KEY, GEMINI_API_KEY, XAI_API_KEY, ... (see `openfix providers`)

semgrep scan --sarif -o semgrep.sarif  # any scanner that writes SARIF or a supported JSON format
openfix plan semgrep.sarif             # what the policy will do with each finding; no model calls
openfix fix semgrep.sarif              # fix, verify, and write receipts to .openfix/runs/<timestamp>/
openfix fix semgrep.sarif --model openai:gpt-5 --reviewer anthropic:claude-opus-5-5 --open-prs
```

Try the whole pipeline without an API key on the bundled vulnerable app, from a clone of this repository:

```bash
pip install -e . semgrep
cd examples/vulnerable-app
openfix fix findings/semgrep.sarif --only path-traversal-path-join-var \
  --model scripted:demo/path-traversal.script.yaml --sandbox local
```

```
→ [high] path-traversal-path-join-var src/files.js:11  [autofix via rule 'code findings']
  verified: all required checks passed (rescan, tests, regression_test)
```

## Commands

| Command | |
|---|---|
| `openfix findings REPORT...` | Normalize and list findings (`--json` for OpenFix findings JSON) |
| `openfix plan REPORT...` | Show each finding's policy decision |
| `openfix fix REPORT...` | Fix, verify, write receipts; `--open-prs`, `--model`, `--reviewer`, `--only`, `--max`, `--require`, `--sandbox`, `--sign` |
| `openfix receipt verify DIR --repo .` | Re-check a receipt's digests and that its patch applies |
| `openfix providers` | Supported providers and credential status |
| `openfix init` | Write a starter `openfix.yaml` |

`--repo` can point at a subdirectory of a monorepo: findings, tests and scans are resolved relative to it, and
patches are written relative to the repository root.

## Policy

```yaml
# openfix.yaml (first matching rule wins)
rules:
  - match: { category: [secrets] }
    action: skip                       # rotate credentials; don't just delete them from code
  - match: { path: ["**/auth/**", "**/payment*/**"] }
    action: propose                    # patch + receipt for a human, no PR
  - match: { category: [sast, sca], min_severity: medium }
    action: autofix                    # PR when every required check passes
guards:
  max_files_changed: 4
  max_lines_changed: 200
  protected_paths: [".github/workflows/**", "**/.env*"]
models:
  author: anthropic:claude-opus-5-5
  reviewer: openai:gpt-5
  local_only_paths: ["services/payments/**"]    # this code is only ever sent to local models
budgets: { max_turns: 40, max_usd_per_fix: 3.0, max_usd_per_run: 25.0 }
verify:
  require: [rescan, tests, regression_test]
```

Full reference: [docs/policy.md](docs/policy.md).

## GitHub Action

```yaml
name: OpenFix
on:
  workflow_dispatch:
  schedule: [{ cron: "0 6 * * 1" }]
permissions:
  contents: write
  pull-requests: write
jobs:
  fix:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install semgrep && semgrep scan --config p/default --sarif -o semgrep.sarif || true
      - uses: markusweldon/openfix@main
        with:
          reports: semgrep.sarif
          model: anthropic:claude-opus-5-5
          reviewer: openai:gpt-5
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

Each verified autofix becomes a draft PR containing the evidence table and the receipt digest. Receipts,
`summary.md` and `openfix.sarif` are uploaded as a workflow artifact. Repository CI still runs on the PR, and a
human still merges it.

## Supported inputs

SARIF 2.1.0 (Semgrep, CodeQL, Snyk Code, Trivy, Checkov, Bandit, Gitleaks, ...), Semgrep JSON, Snyk Open Source
JSON, Trivy JSON (vulnerabilities, misconfigurations, secrets), OSV-Scanner JSON, Gitleaks JSON, GitHub
code-scanning alerts, GitHub Dependabot alerts, and [OpenFix findings JSON](docs/findings-format.md). Reports
are detected automatically, and secret values are never stored.

## Documentation

- [Policy reference](docs/policy.md)
- [Providers and models](docs/providers.md)
- [Verification and receipts](docs/receipts.md)
- [Security model](docs/security-model.md): what OpenFix protects against, and what it doesn't
- [Findings format](docs/findings-format.md)
- [Roadmap](ROADMAP.md)

## Status

OpenFix 0.3 is alpha. The core pipeline (ingest, policy, agent, verification, receipts, PRs) is implemented and
tested end to end against real repositories, scanners and test suites. See the [roadmap](ROADMAP.md) for what's
next: a public fix-rate benchmark across models, an MCP server, and GitLab support.

## License

MIT
