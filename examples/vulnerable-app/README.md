# Example: intentionally vulnerable app

**Do not deploy.** This small Node app contains ten deliberate vulnerabilities (path traversal, command injection,
eval, SQL injection, XSS, unsafe `vm`, `execFile` with a shell, weak crypto, prototype pollution, and a hardcoded
token), as well as outdated dependencies.

- `.semgrep.yml`: local Semgrep rules, so the scan is offline and reproducible
- `findings/semgrep.sarif`: the report those rules produce
  (`semgrep scan --config .semgrep.yml --sarif -o findings/semgrep.sarif src`)
- `findings/snyk-code.sarif`: a Snyk Code report for the same app (`snyk code test --sarif-file-output=findings/snyk-code.sarif .`)
- `openfix.yaml`: the policy (secrets skipped; code findings autofixed; rescan, tests and regression test required)
- `demo/path-traversal.script.yaml`: recorded tool calls for the `scripted` provider
- `demo/snyk-and-semgrep.script.yaml`: one recorded fix per finding, for the Snyk plus Semgrep run below

```bash
openfix plan findings/semgrep.sarif
openfix fix findings/semgrep.sarif --only path-traversal-path-join-var \
  --model scripted:demo/path-traversal.script.yaml --sandbox local      # no API key needed
openfix fix findings/snyk-code.sarif findings/semgrep.sarif \
  --only javascript/CommandInjection,path-traversal-path-join-var \
  --model scripted:demo/snyk-and-semgrep.script.yaml --sandbox local   # two scanners; Snyk rescans need `snyk auth`
openfix fix findings/semgrep.sarif --model anthropic:claude-opus-5-5 --sandbox local --max 3   # a real model
```
