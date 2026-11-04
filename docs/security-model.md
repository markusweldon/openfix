# Security model

OpenFix gives a language model write access to source code, in a security context. That makes the harness around
the model part of the security boundary. This page states what OpenFix defends against and what it doesn't.

## Assets and trust

| Input | Trusted? | Handling |
|---|---|---|
| Policy file | yes: whoever controls the repository controls the policy | parsed strictly; unknown keys rejected |
| Scanner reports | **no** | treated as data; shown to the model inside `<untrusted_finding>`; secret values dropped or redacted |
| Repository contents | **no** (may contain prompt injection, or malicious tests) | read through tools; executed only in the sandbox |
| Model output | **no** | can only call the listed tools; every write is policy-checked; verified independently |
| API keys / tokens | secret | never in the sandbox environment, prompts or receipts |

## Controls

- **No ambient authority for the model.** There is no shell, no network, and no git. File access is confined to the
  checkout: absolute paths, `..`, symlink writes and `.git` are refused. Protected paths, file-count and line-count
  limits are enforced on every write and again on the final patch.
- **Isolation.** All work happens in a disposable `git worktree`, so the user's checkout is never touched. Tests run
  in a fresh container per command: `--network none` by default, all capabilities dropped, `no-new-privileges`,
  memory, CPU and PID limits, and the host user rather than root. Only the setup step (dependency install) gets
  network access, and the defaults pass `--ignore-scripts`.
- **Secret hygiene.** Commands run with an environment scrubbed of anything resembling a key, token, password or
  session. Output and receipts pass through redaction of common credential formats. Scanner credentials (for example
  `SNYK_TOKEN`) are passed only to the scanner process, which doesn't execute repository code.
- **Prompt-injection resistance.** The system prompt marks findings and file contents as data. Injection can still
  steer a model, which is why the outcome is never accepted on the model's word: rescan, tests, the differential
  regression test and an optional second-model review decide.
- **No silent dismissals.** A model that says "false positive" produces a `disputed` record with its reasoning. It
  never suppresses or closes the finding.
- **Humans merge.** OpenFix opens draft PRs only for `autofix` + `verified` and never merges. Repository CI and branch
  protection still apply.

## Known limits

- `--sandbox local` runs the repository's tests on the host. Use it only for trusted code or on ephemeral CI
  runners.
- Docker isolation is a strong default but not a VM boundary. For hostile code, run OpenFix inside a VM or
  gVisor/Kata runtime.
- A scanner that doesn't reproduce the finding, or a project without tests, limits what can be proven. Receipts say
  `unverified` in those cases rather than pretending otherwise.
- Redaction is pattern-based, and an unusual secret format can slip through. Configure `local_only_paths` for code
  that must not leave your infrastructure.
- Rule-id matching between the report and the rescan tolerates prefixes (Semgrep adds the config path). Configure
  `verify.scanner` to run the same rules that produced the report.

Report vulnerabilities in OpenFix itself as described in [SECURITY.md](../SECURITY.md).
