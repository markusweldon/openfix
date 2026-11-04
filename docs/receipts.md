# Verification and receipts

## How a fix is verified

For every finding the policy doesn't skip, OpenFix creates a disposable `git worktree` of the current commit. Your
working tree is never modified. Then:

1. **Baseline.** The scanner runs on the original code. If it doesn't reproduce the finding and `rescan` is required,
   the finding is marked `not_reproduced` and **no model is called**. The test suite runs on the original code to
   record whether it was already failing.
2. **Fix.** A direct dependency upgrade is applied deterministically when possible. Otherwise the agent works through
   a small set of tools: `list_files`, `read_file`, `search`, `edit_file`, `write_file`, `run_tests`, `rescan`,
   `submit` and `give_up`.
3. **Guards.** The exact patch is re-checked against the policy limits.
4. **Checks** on the patched code:

| Check | `passed` | `failed` | `inconclusive` / `not_run` |
|---|---|---|---|
| `rescan` | reproduced before, absent after | still reported after the patch | not reproduced before, or scanner unavailable |
| `tests` | suite passes after the patch | fails after, passed before | already failed before, or no test command |
| `regression_test` | the new test fails on the original code and the suite passes with the fix | the test passes on the original code (it proves nothing) | no new test, or the suite already failed |
| `review` | the reviewer approves and says the root cause is fixed | the reviewer requests changes | no reviewer, or no valid verdict |

Matching a finding across the patch follows line moves: the original line number is mapped through the diff, so a
finding is still recognized after code around it changes.

5. **Status.** `verified` if every required check passed, `failed` if any check failed, otherwise `unverified`.

## Output

```
.openfix/runs/20261104T175402Z/
  summary.json  summary.md  openfix.sarif        # whole run; SARIF includes fixes[] for each patch
  of-d648afa68ad0/
    patch.diff        # exact change, relative to the repository root
    receipt.json      # in-toto Statement v1, subject = sha256(patch.diff)
    pr-body.md        # the pull request description
    agent-log.json    # every tool call (arguments truncated), refusals, token usage
```

## Receipt format

```json
{
  "_type": "https://in-toto.io/Statement/v1",
  "subject": [{ "name": "patch.diff", "digest": { "sha256": "36cd2f68..." } }],
  "predicateType": "https://github.com/markusweldon/openfix/receipt/v1",
  "predicate": {
    "status": "verified",
    "finding": { "tool": "Semgrep OSS", "rule_id": "path-traversal-path-join-var", "...": "..." },
    "policy": { "decision": { "action": "autofix", "rule": "code findings", "...": "..." }, "policy_sha256": "..." },
    "repository": { "base_commit": "9b3f760c..." },
    "patch": { "sha256": "36cd2f68...", "files": [{ "path": "src/files.js", "added": 5, "removed": 2 }] },
    "fixer": "agent",
    "author": { "model": "anthropic:claude-opus-5-5", "turns": 9, "usage": { "...": "..." }, "cost_usd": 0.41 },
    "checks": [{ "name": "rescan", "status": "passed", "detail": "...", "evidence": { "...": "..." } }]
  }
}
```

Evidence includes the commands that were run, their exit codes and durations, and the tail of their output, with
credentials redacted.

## Verifying and signing

```bash
openfix receipt verify .openfix/runs/<run>/<finding> --repo .
```

This checks the statement type, that `patch.diff` matches the subject digest and the predicate, that the base commit
exists, and that the patch still applies.

With `--sign`, OpenFix calls `cosign sign-blob --bundle` on the receipt (keyless Sigstore in CI) and writes
`receipt.sigstore.json`. Verify it with `cosign verify-blob --bundle ...` and the identity of the workflow that
signed it.
