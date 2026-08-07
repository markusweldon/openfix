# OpenFix — Field Eng demo cheat sheet

Aligned to the Cursor Field Engineering SDK exercise: live prototype, architecture, trade-offs, limitations/evolve, **extend live**.

## 1. Problem (Example B) — open with this (~1 min)

Enterprise scanners (Semgrep, Snyk, GHAS, …) dump noisy SARIF. Engineers ignore it; SLAs burn.

**OpenFix:** scanner findings in → deterministic policy → Cursor **cloud** agents open fix PRs → humans authorize.

Agents do **not** scan or self-attest. Detect ≠ remediate ≠ authorize.

## 2. Live command script (~15–18 min)

```bash
cd ~/dev/openfix

# Optional: wipe local remediations so auto_fix queue is full again
# rm -rf .openfix

npx tsx src/cli.ts ingest fixtures/findings/demo.sarif
# Prints openfixRunId + repoUrl (+ commitSha if OPENFIX_COMMIT_SHA / GITHUB_SHA set)
# Multi-artifact (merge + fingerprint dedupe): 
# npx tsx src/cli.ts ingest fixtures/findings/demo.sarif fixtures/findings/extra.json
# Optional MCP-style door (stub): npx tsx src/cli.ts ingest --from simulated:semgrep
npx tsx src/cli.ts triage
# Expect: OpenFix run line, then auto_fix / human_only / suppress_noise

npx tsx src/cli.ts remediate
# Finding-lane board: SEV | FINDING | LOCATION | STATUS (spinner while running)

# Concurrent lanes
npx tsx src/cli.ts remediate --agents 2
# or: npx tsx src/cli.ts remediate -n 2
# After: ── Fleet ── lists each bc-… — resume that id (not only --last)
# Full agent stream: npx tsx src/cli.ts remediate -n 2 --verbose

npx tsx src/cli.ts status --last
npx tsx src/cli.ts resume --last --prompt "Address review feedback: strengthen the regression test and note CI must re-run the scanner before merge."
npx tsx src/cli.ts verify --last
# Compact App CI poll (Unit tests + Scanner re-run). Full gates: verify --checklist
```

Then browser: open the **PR** → Files (provenance + scanner re-run language) → **Checks**.

**Draft PRs are expected:** Cursor cloud `autoCreatePR` opens **draft** PRs by default — leave them draft until a human is ready to review.

**Verify / CI:** OpenFix does not re-scan. App repo workflow **CI** runs on the remediation PR (`pull_request`) with **2 lean jobs:** Unit tests + Scanner re-run stub. `verify --last` polls check-runs (compact); `verify --checklist` prints the full pre-merge gate list.

**Async / multi-step:** Multi-step lane = ingest → triage → remediate → verify. Async = durable cloud `bc-` id; status/resume anytime.

**Messy paste OK:** `status agent=bc-…` or `status bc-… run=run-…` — we parse the `bc-` token.

## 2b. Hosting & Actions — talk track (~45 sec if asked)

**Objection:** “If it’s a GitHub Action, isn’t this just a script?”

**Answer:** Actions is the **hook**, not the product — same pattern as Dependabot / CodeQL. The runner only invokes OpenFix; **work** is Cursor cloud agents (`bc-…`), durable and resumable. Policy + run context + draft PRs + App CI are the control plane.

**What you host / own**

| Piece | Where it lives | Who runs it |
| --- | --- | --- |
| OpenFix package | Org reusable workflow **or** published Action (this repo today) | Thin job: checkout → `ingest` → `triage` → `remediate` |
| Secrets | App repo (or org) Actions secrets | `CURSOR_API_KEY` (required). No target-URL secret when the Action runs *in* the app repo |
| Policy | `policy.yaml` in OpenFix (or org-central override later) | Security / platform owns gates |
| Agents | Cursor cloud (Cursor hosts the VMs) | You don’t run agent infra |
| Verify gates | App repo `CI` workflow | Unit + scanner re-run before merge |

**Enterprise install path (say this)**

1. Publish OpenFix as an **org reusable workflow** (one version, many apps).  
2. In each app repo: after scanners upload SARIF → call that workflow (`workflow_call` / `workflow_run`).  
3. Same-repo context: `GITHUB_REPOSITORY` + `github.sha` bind findings to the scanned snapshot.  
4. Agents open **draft** fix PRs; humans + App CI authorize.

**Scale model:** fan-out — same lane in every app pipeline — not one mega-job remediating the company. Concurrency / `getUsage` budgets are org policy on top.

**Today vs next (one breath):** Demo = CLI + manual `workflow_dispatch` in this repo. Production = reusable workflow after real SARIF; optional platform API later if you outgrow Actions as the only trigger.

## 3. Design decisions / trade-offs

| Choice | Why |
| --- | --- |
| SARIF ingest | Vendor-agnostic; CI interchange; not another scanner silo |
| Multi-file ingest | `ingest a.sarif b.json` merges artifacts; fingerprint dedupe (exact overlaps) |
| `policy.yaml` outside the model | Enterprise control plane; live-extend without touching agent prompts |
| Cloud agents + `autoCreatePR` | Durable jobs, real PR artifact, matches software-factory story |
| Local CLI: `OPENFIX_TARGET_REPO` in `.env` | Laptop remediates a remote app repo; no Actions context |
| Same-repo Actions: derive from `GITHUB_*` | Action installed in the app repo → `GITHUB_REPOSITORY` / `github.sha` are the target |
| OpenFix run context at ingest | Binds findings → repo URL + commit SHA + run id; shown on ingest/triage; used by remediate |
| Finding-lane board UI | Finding rows update in place; STATUS may show short agent hints; `--verbose` for full streams |
| Fleet summary lists `bc-…` | After `--agents N`, each lane’s agent id is printable for `status` / `resume` (not only `--last`) |
| Lean App CI (2 jobs) | Fast free-tier Checks; stubs stand in for Semgrep/OSV/CodeQL |
| Simulated MCP ingest | Optional `--from simulated:semgrep`; SARIF remains the CI contract |

## 4. Real now vs next (enterprise scale)

| Real in this demo | Next (honest evolution) |
| --- | --- |
| One app repo + one SARIF | Same OpenFix job wired after scanner upload in **each** service repo |
| CLI `remediate` / `--agents 2` | GitHub Action matrix or per-repo workflow; concurrency = factory workers |
| Deep `auto_fix` queue in fixtures | Production queue depth from real scanner noise + policy gates |
| `--all-auto` capped by `OPENFIX_MAX_CONCURRENT` | Cost budgets via `Agent.getUsage` + org-wide caps |

**Scale framing:** SARIF is already per application. Enterprise scale is the same remediation lane in every app’s pipeline — not one mega-orchestrator that owns the org.

## 5. Limitations → evolution

| Limitation now | Evolve to |
| --- | --- |
| Manual CLI kickoff | GitHub Action `OpenFix: SARIF → fix PRs` after scanner `workflow_run` |
| Local CLI needs `OPENFIX_TARGET_REPO` | Put the Action in each app repo (`GITHUB_REPOSITORY` is the target). Override only if the workflow remediates a *different* repo than the one running the job |
| Simple policy | Reachability, CODEOWNERS, severity SLAs |
| Scanner stub on app CI | Real Semgrep/CodeQL/OSV as required checks; `verify` already polls via `gh` |
| Remediate used to exit 0 on agent error | Fixed — non-zero if status ≠ finished or no PR |
| No cost caps in UI | `Agent.getUsage` budgets per finding |
| Simulated MCP ingest only | Real Semgrep/Snyk MCP clients behind the same Finding adapter |

## 6. Live-extend menu (practice today)

| If they say… | You do / say… |
| --- | --- |
| “Isn’t Actions just a script?” | Hook vs product — see §2b; agents + policy are the system |
| Block another path | Edit [`policy.yaml`](policy.yaml) — add `payments` under `sensitive_path_segments` → `triage` |
| Fix a specific finding | `npx tsx src/cli.ts remediate --fingerprint semgrep-cmdi-001` |
| Concurrent factory | `npx tsx src/cli.ts remediate --agents 2` |
| Drain queue (warn: time/cost) | `npx tsx src/cli.ts remediate --all-auto` |
| Reviewer feedback | `npx tsx src/cli.ts resume --last --prompt "…"` |
| Prove it’s fixed | `verify --last` (compact App CI poll) + PR Checks tab |
| Another service | Change `OPENFIX_TARGET_REPO` in `.env` only (demo); prod = Action in that repo |

### Live-extend rehearsal (policy)

1. `npx tsx src/cli.ts ingest fixtures/findings/demo.sarif && npx tsx src/cli.ts triage`
2. Open `policy.yaml`, add `- payments` under `sensitive_path_segments`
3. `npx tsx src/cli.ts triage` again — same findings, new gate; agents never see payments paths for `auto_fix`.
4. Revert the YAML line after (or leave it and explain).

## Files to open if they dive into code

| File | Story |
| --- | --- |
| `src/cli.ts` | Pipeline commands + concurrent remediate / lane board wiring |
| `src/cli/helpers.ts` | `LaneBoard` (in-place STATUS + spinner), fleet/next helpers |
| `src/config.ts` | `OPENFIX_*` overrides + `GITHUB_*` derivation (repo / SHA / run id) |
| `src/state/store.ts` | Findings + remediations + `currentRun` / `.openfix/runs/` |
| `policy.yaml` | Live-extend control plane |
| `src/policy/engine.ts` | Deterministic triage |
| `src/remediator/agent.ts` | Cursor SDK cloud create/stream/wait/resume; uses run context |
| `src/ingest/load.ts` | SARIF / findings JSON → Finding |
| `src/ingest/simulated-mcp.ts` | Optional MCP-style adapter stub (`ingest --from …`) |
| `src/remediator/prompt.ts` | Separation of duties + scanner re-run gate |
| `src/verify.ts` | Compact App CI poll (+ optional `--checklist`) |
