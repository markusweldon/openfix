# Roadmap

## 0.3 (this release, alpha)

- Ingest SARIF, Semgrep, Snyk, Trivy, OSV-Scanner, Gitleaks, GitHub code scanning and Dependabot
- Policy as code: actions, guards, budgets, per-rule models, local-only paths
- Providers: Anthropic, OpenAI and every OpenAI-compatible API (xAI, OpenRouter, Groq, DeepSeek, Mistral, Together,
  Fireworks, Ollama, vLLM, LM Studio), Gemini, and a scripted provider
- Agent with policy-checked tools; Docker or local sandbox
- Verification: rescan before and after, tests, differential regression test, cross-model review
- Deterministic dependency upgrades (npm, pip)
- In-toto receipts, Sigstore signing, `receipt verify`, SARIF output with `fixes[]`
- GitHub draft PRs and a composite GitHub Action; monorepo project directories

## Next

1. **OpenFix Bench.** A public corpus of real vulnerable commits with known fixes, plus `openfix bench --model X`,
   reporting the *verified* fix rate, cost per verified fix, and how often a fix was wrongly accepted. Published as
   a leaderboard across providers.
2. **MCP server.** Expose `plan`, `fix` and `receipt verify` as MCP tools, so any agent host can request a verified
   fix.
3. **GitLab and Bitbucket** merge requests; SARIF upload back to GitHub code scanning.
4. **More deterministic fixers**: lockfile-aware upgrades for pnpm/yarn, Go modules, Maven/Gradle, Cargo, and
   transitive overrides.
5. **Grouping.** One PR per rule or per package, and de-duplication of the same root cause across findings.
6. **Stronger isolation**: gVisor or Firecracker runners, and an egress allowlist for the setup step.
7. **Exploit-oriented validation**: optional dynamic checks (a generated proof-of-concept request against a test
   server) for web vulnerability classes.
