# Policy reference

OpenFix reads the first of `openfix.yaml`, `openfix.yml`, `.openfix.yaml` or `.github/openfix.yaml` in the project
directory, or the file passed with `--policy`. Without one, it uses built-in defaults (`openfix init` writes them
out). Unknown keys are rejected so typos don't silently weaken a policy.

The policy is evaluated by code, never by the model. Findings that are skipped are never sent to a model.

## Actions

| Action | Behavior |
|---|---|
| `autofix` | Generate a fix, verify it, write a receipt, and open a draft PR (with `--open-prs`) if every required check passes. |
| `propose` | Generate and verify a fix, then write the patch and receipt for a human to apply. Never opens a PR. |
| `skip` | Do nothing. The reason is recorded in the run summary. |

## Rules

`rules` is an ordered list, and the **first match wins**. If no rule matches, `default_action` applies (default `propose`).

```yaml
rules:
  - name: sql injection goes to a human first
    match: { cwe: [CWE-89] }
    action: propose
  - match: { tool: [semgrep, codeql], category: [sast], min_severity: medium }
    action: autofix
    author: openai:gpt-5              # optional per-rule model
    require: [rescan, tests, review]  # optional per-rule verification
```

Every `match` field is optional, and all given fields must match:

| Field | Matches |
|---|---|
| `tool` | scanner name (case-insensitive) |
| `rule` | glob on the rule id, e.g. `"*sql*"` |
| `category` | `sast`, `sca`, `secrets`, `iac`, `container`, `other` |
| `severity` | exact severities: `critical`, `high`, `medium`, `low`, `info` |
| `min_severity` | this severity or higher |
| `cwe` | any of these CWE ids |
| `path` | glob on the finding's file (or dependency manifest); `**` spans directories |

### Built-in defaults

1. `secrets` → **skip**. A leaked credential must be rotated, and deleting it from code doesn't revoke it.
2. `info` → **skip**
3. `iac`, `container` → **propose**
4. `**/auth/**`, `**/crypto/**`, `**/*crypt*`, `**/iam/**`, `**/payment*/**` → **propose**
5. `sca` → **autofix**
6. `sast` at `low` or above → **autofix**

## Guards

Checked on every write the agent attempts, and again on the final patch.

| Key | Default | |
|---|---|---|
| `max_files_changed` | 4 | |
| `max_lines_changed` | 200 | added + removed |
| `protected_paths` | `.git/**`, `.github/workflows/**`, `**/.env`, `**/.env.*`, `openfix.yaml` | never writable |
| `allow_new_dependencies` | `false` | a patch that adds a dependency to `package.json` fails |

## Models

| Key | Default | |
|---|---|---|
| `author` | `anthropic:claude-opus-5-5` | writes the fix; `--model` overrides |
| `reviewer` | none | reviews the diff; `--reviewer` overrides. Prefer a different provider. |
| `effort` | `high` | reasoning effort, where the provider supports it |
| `local_only_paths` | `[]` | findings in these paths are only sent to local providers (`ollama`, `vllm`, `lmstudio`, or a `compat` endpoint on localhost) |

## Budgets

| Key | Default |
|---|---|
| `max_turns` | 40 |
| `max_tokens_per_fix` | 600000 |
| `max_usd_per_fix` | 3.0 |
| `max_usd_per_run` | 25.0 |

Dollar limits apply when the price is known. Claude prices are built in, and you can add others:

```yaml
pricing:
  "openai:gpt-5": [1.25, 10.0]       # USD per million input, output tokens
```

## Verify

| Key | Default | |
|---|---|---|
| `require` | `[rescan, tests]` | checks that must **pass** for `verified`; also `regression_test`, `review` |
| `tests` | auto-detected | `{command, timeout}`: npm test, pytest, go test, cargo test, mvn, gradle |
| `setup` | auto-detected | `{command, timeout}` run once with network access, e.g. `npm ci --ignore-scripts` |
| `scanner` | from the finding's tool | a preset name (`semgrep`, `snyk-code`, `snyk`, `trivy`, `osv-scanner`, `gitleaks`, `bandit`) or `{command}` that writes SARIF to `{output}` |

A fix is `verified` only when every required check passed, `failed` when any check failed, and `unverified`
otherwise (for example, the scanner isn't installed, or the tests already failed before the change).

## Sandbox and pull requests

```yaml
sandbox:
  backend: auto        # docker when available, else refuse; "local" runs commands on this machine
  image: null          # default chosen from the project (node, python, go, rust, java)
  network: false
  memory: 2g
  cpus: "2"
pull_requests:
  draft: true
  labels: [security, openfix]
  branch_prefix: openfix/
```
