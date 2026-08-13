# AGENTS.md

## Cursor Cloud specific instructions

OpenFix is a TypeScript ESM CLI (Node `>=22.13.0`) built on the Cursor SDK. It is a
control plane, not a scanner: `ingest` normalizes SARIF/JSON findings, `triage`
applies deterministic policy (`policy.yaml`), and `remediate`/`status`/`resume`
drive Cursor **cloud** agents that open remediation PRs. There is no long-running
server or UI — everything is invoked via the CLI.

### Running the CLI
- Dev (no build needed): `npm run dev -- <command>` (runs `tsx src/cli.ts`). Example: `npm run dev -- ingest fixtures/findings/demo.sarif` then `npm run dev -- triage`.
- Standard scripts are in `package.json`: `typecheck` (`tsc --noEmit`), `build` (`tsc` → `dist/`). There is no `lint` script (no ESLint config); `typecheck` is the closest gate. There is no `test` script — the repo has no automated tests for the orchestrator (the JS/tests under `fixtures/vulnerable-app/` are demo fixtures, not this project's tests).

### What runs offline vs. what needs secrets
- `ingest` and `triage` run fully locally with no credentials — this is the core deterministic pipeline to exercise end-to-end.
- `remediate`, `status`, `resume` require `CURSOR_API_KEY` and a target repo (`OPENFIX_TARGET_REPO`, or `GITHUB_REPOSITORY` in Actions). Without these they fail fast with a clear message. Running them spawns **real** Cursor cloud agents that open PRs against the target repo, so only run them with valid secrets and an intended target.
- `verify` shells out to the GitHub CLI (`gh`) to poll App CI on a fix PR; without `--pr`/`--last` it just prints usage.

### State / gotchas
- Runtime state is written to `.openfix/` (git-ignored): `state.json` plus per-run context under `.openfix/runs/`. `ingest` overwrites current findings, so re-run `ingest` before `triage`/`remediate` if state was changed by another command. To reset the demo queue: `rm -rf .openfix`.
- Config comes from env / `.env` (see `.env.example`); never commit `.env` or `.openfix/`.
- `.cursor/hooks/` enforce preventative controls (block force-push / push to main). Always open a PR; never push to `main`.
