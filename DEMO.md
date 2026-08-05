# OpenFix — Field Eng demo cheat sheet

Aligned to the Cursor Field Engineering SDK exercise: live prototype, architecture, trade-offs, limitations/evolve, **extend live**.

## 1. Problem (Example B) — say this first (~1 min)

Enterprise scanners (Semgrep, Snyk, GHAS, …) dump noisy SARIF. Engineers ignore it; SLAs burn.

**OpenFix:** scanner findings in → deterministic policy → Cursor **cloud** agents open fix PRs → humans authorize.

Agents do **not** scan or self-attest. Detect ≠ remediate ≠ authorize.

## 2. Live command script (~15–18 min)

```bash
cd ~/dev/openfix

# Interview-morning hygiene (optional): wipe local remediations so auto_fix is full
# rm -rf .openfix

npx tsx src/cli.ts ingest fixtures/findings/demo.sarif
npx tsx src/cli.ts triage
# Point at: auto_fix queue (severity-ordered, 10+) vs human_only (auth secret) vs noise

npx tsx src/cli.ts remediate
# LIVE one cloud agent — stream output — copy bc-… / PR URL (or use --last after)

# Scale beat (optional, ~2 min): concurrent labeled streams + fleet summary
npx tsx src/cli.ts remediate --agents 2
# or: npx tsx src/cli.ts remediate -n 2

npx tsx src/cli.ts status --last
npx tsx src/cli.ts resume --last --prompt "Address review feedback: strengthen the regression test and note CI must re-run the scanner before merge."
npx tsx src/cli.ts verify --last
```

Then browser: open the **PR** → Files (provenance + scanner re-run language) → **Checks** (App CI).

**Async / multi-step one-liner:**  
*Multi-step lane = ingest → triage → remediate → verify. Async = durable cloud `bc-` id; status/resume anytime.*

**Messy paste OK:** `status agent=bc-…` or `status bc-… run=run-…` — we parse the `bc-` token.

**Backup PR:** https://github.com/markusweldon/openfix-vulnerable-app/pull/1

## 3. Design decisions / trade-offs

| Choice | Why |
| --- | --- |
| SARIF ingest | Vendor-agnostic; CI interchange; not another scanner silo |
| `policy.yaml` outside the model | Enterprise control plane; live-extend without touching agent prompts |
| Cloud agents + `autoCreatePR` | Durable jobs, real PR artifact, matches software-factory story |
| One `OPENFIX_TARGET_REPO` in `.env` | Config, not hardcode — point at another service tomorrow |
| PR never auto-merge | Humans authorize; branch protection + App CI verify |
| Fixture SARIF (not live Snyk API) | Reliable demo; format is what matters |
| Concurrent `--agents N` | Fan-out inside one app's queue; org scale = same lane in many pipelines |

## 4. Real now vs next (enterprise scale)

| Real in this demo | Next (honest evolution) |
| --- | --- |
| One app repo + one SARIF | Same OpenFix job wired after scanner upload in **each** service repo |
| CLI `remediate` / `--agents 2` | GitHub Action matrix or per-repo workflow; concurrency = factory workers |
| Deep `auto_fix` queue in fixtures | Production queue depth from real scanner noise + policy gates |
| `--all-auto` capped by `OPENFIX_MAX_CONCURRENT` | Cost budgets via `Agent.getUsage` + org-wide caps |

**Say this out loud:** *“We are not building a multi-repo router for the interview. SARIF is already per application. Enterprise scale is the same remediation lane running in every app’s pipeline — not one mega-orchestrator that owns the org.”*

## 5. Limitations → evolution

| Limitation now | Evolve to |
| --- | --- |
| Manual CLI kickoff | GitHub Action `OpenFix: SARIF → fix PRs` after scanner `workflow_run` |
| One target repo in `.env` | Per-service `OPENFIX_TARGET_REPO` in each pipeline (same code) |
| Simple policy | Reachability, CODEOWNERS, severity SLAs |
| Scanner re-run stub on app | Real Semgrep/CodeQL on fix PR as required check |
| No cost caps in UI | `Agent.getUsage` budgets per finding |

## 6. Live-extend menu (practice today)

| If they say… | You do… |
| --- | --- |
| Block another path | Edit [`policy.yaml`](policy.yaml) — add `payments` under `sensitive_path_segments` → `triage` |
| Fix a specific finding | `npx tsx src/cli.ts remediate --fingerprint semgrep-cmdi-001` |
| Concurrent factory | `npx tsx src/cli.ts remediate --agents 2` |
| Drain queue (warn: time/cost) | `npx tsx src/cli.ts remediate --all-auto` |
| Reviewer feedback | `npx tsx src/cli.ts resume --last --prompt "…"` |
| Prove it’s fixed | `verify --last` + PR Checks |
| Another service | Change `OPENFIX_TARGET_REPO` in `.env` only |

### Live-extend rehearsal (policy)

1. `npx tsx src/cli.ts ingest fixtures/findings/demo.sarif && npx tsx src/cli.ts triage`
2. Open `policy.yaml`, add `- payments` under `sensitive_path_segments`
3. `npx tsx src/cli.ts triage` again — narrate: *“same findings, new gate; agents never saw payments paths.”*
4. Revert the YAML line after (or leave it and explain).

## Files to open if they dive into code

| File | Story |
| --- | --- |
| `src/cli.ts` | Pipeline commands + concurrent remediate |
| `policy.yaml` | Live-extend control plane |
| `src/policy/engine.ts` | Deterministic triage |
| `src/remediator/agent.ts` | Cursor SDK cloud create/stream/wait/resume |
| `src/ingest/load.ts` | SARIF → Finding |
| `src/remediator/prompt.ts` | Separation of duties + scanner re-run gate |
