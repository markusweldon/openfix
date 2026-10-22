# OpenFix walkthroughs

There are two runnable paths: a standalone lifecycle simulation and the existing Cursor remediation CLI. They exercise different code and do not form an integrated application yet. For the live customer exercise, begin with the [discovery workbook](docs/prep/exercise-workbook.md); no presentation or prepared demo is required.

Use the [repository plan](docs/prep/repo-strategy.md) to discuss the next increment and the [verification record](docs/prep/validation.md) for the checks actually performed. The examples below are instructions, not claims that a live scan or remediation was run.

## A. Lifecycle simulation: inspect the proposed decision gates

From the repository root, with Node.js 22.13 or later:

```bash
npm install
npm run test:lifecycle
npm run demo:lifecycle
```

The demo prints an explicit simulation banner and moves a hypothetical cross-tenant invoice finding through candidate, validation, acceptance, patch, verification, review, rollout, revalidation and closure states. Actors, revisions, patch hash, evidence, checks and rollout are fabricated. No model, scan, merge or deployment runs.

To save the simulated record to a new local file:

```bash
npm run demo:lifecycle -- --out /tmp/openfix-simulated-case.json
```

The command refuses to overwrite an existing file. The record is useful for inspecting evidence fields and decision events; it is not evidence that the hypothetical vulnerability exists or was fixed.

Explain the modeled boundaries:

- A candidate needs validation evidence before acceptance and remediation.
- Verification and review refer to an exact patch identity. A changed patch invalidates prior verification and approval.
- Failed or incomplete required checks prevent modeled readiness. Closure follows recorded rollout and revalidation.
- Actor IDs and role labels are supplied by the caller. The model does not authenticate users, execute verification, persist operational cases or enforce production access control.

The [tests](tests/lifecycle.test.mjs) exercise negative cases such as missing evidence, unvalidated findings, disproved candidates, stale verification and premature closure. A passing test suite establishes these software behaviors, not model accuracy or production assurance.

## B. Current v1 CLI: imported finding to Cursor fix PR

This path uses the existing scanner-oriented application. Ingest and triage are local; remediation and resume use Cursor cloud and may create or update remote PRs. Live use requires a Cursor API credential and repository access. ChatGPT Pro does not authenticate this executor; see the [product map](docs/prep/product-landscape.md) for separate OpenAI surface and billing guidance.

Configure `.env` using [.env.example](.env.example):

| Variable | Purpose |
| --- | --- |
| `CURSOR_API_KEY` | Cursor cloud authentication |
| `OPENFIX_TARGET_REPO` | Repository the agent will change |
| `OPENFIX_COMMIT_SHA` | Actual revision represented by the imported report |
| `OPENFIX_STARTING_REF` | Optional clone ref when no scan commit is recorded; remediation prefers a stored scan commit |
| `OPENFIX_MAX_CONCURRENT` | Concurrent-job cap, default 2 |

For a credible end-to-end result, use a report produced from that repository and immutable revision. Configure the target before ingesting, and re-ingest the matching report after changing it: remediation prefers stored ingest context over later environment changes. The checked-in fixtures demonstrate import and policy; they do not establish the target's current vulnerabilities. Preserve existing `.openfix/` records when comparing attempts.

### Import and explain routing

```bash
npm run openfix -- ingest fixtures/findings/demo.sarif
npm run openfix -- triage
```

`ingest` prints the run ID, source and available repository/revision context, then writes local state and a run record. `triage` explains the `auto_fix`, `human_only` and `suppress_noise` buckets from [policy.yaml](policy.yaml). Imported claims have not been independently validated. The queue is principally severity-ordered.

Optional local examples:

```bash
npm run openfix -- ingest fixtures/findings/demo.sarif fixtures/findings/extra.json
npm run openfix -- ingest --from simulated:semgrep
```

Multi-file ingest deduplicates exact fingerprints. The simulated adapter is a stub, including the `mcp:` aliases; it makes no live scanner or MCP call.

### Start a bounded cloud job and retain its identity

After checking the target, revision, routing and intended remote changes:

```bash
npm run openfix -- remediate
npm run openfix -- status --last
```

The default board shows finding, location and progress. Its final summary lists each durable `bc-…` agent ID and PR URL. The prompt requests a draft PR with provenance and test guidance; inspect the resulting PR description, diff, draft status and checks. Prompt instructions alone do not establish a production authorization boundary.

For a specific eligible finding or a concurrent batch:

```bash
npm run openfix -- remediate --fingerprint semgrep-cmdi-001
npm run openfix -- remediate --agents 2
```

`--verbose` prints the full stream. `--all-auto` currently starts one batch up to the concurrency cap; it does not repeatedly drain the remaining queue. Every additional job can consume cloud usage and create another PR. Remediation exits nonzero for thrown, unsuccessful or no-PR outcomes.

### Respond to review and observe CI

Use the specific agent ID from the summary when several jobs exist:

```bash
npm run openfix -- status bc-EXAMPLE
npm run openfix -- resume bc-EXAMPLE --prompt "Address the review feedback and strengthen the regression test."
npm run openfix -- verify --last
npm run openfix -- verify --pr https://github.com/OWNER/REPO/pull/NUMBER --checklist
```

`status` and `resume` also support `--last`. CI polling needs `gh` authenticated for the PR's repository. Review the actual changed head revision and check results after a follow-up changes the patch.

**`verify` is a CI observer.** It does not reproduce the vulnerability, run a scanner or independently validate the fix. It returns nonzero for observed failures but zero for pending or unavailable checks, and it does not enforce a named set of required checks. Skipped or neutral results cannot satisfy a required proof obligation. The companion demo application's scanner job is a placeholder, so its green status supplies no scanner assurance.

To establish a fix, agree the proof first: finding evidence and prerequisites, the original failure where reproducible, legitimate behavior, security and regression checks at the exact changed revision, reviewer acceptance, and the customer's normal merge/deployment controls. Preserve failed, inconclusive and missing proof. The current CLI does not implement that complete evidence workflow.

## Actions and the next integration

The checked-in [OpenFix remediation workflow](.github/workflows/openfix-remediate.yml) is a manual `workflow_dispatch` entry point for the same CLI. In same-repository Actions, target and revision derive from `GITHUB_REPOSITORY` and `GITHUB_SHA` unless overridden. An input SARIF file still needs to represent that revision.

Automatic scanner triggers, reusable `workflow_call` packaging, a published Action, global cost controls and the lifecycle workbench are proposed work. The customer architecture should choose the smallest useful integration; a hosted control plane is not required for every pilot.

## Useful files to inspect

| File | What it demonstrates |
| --- | --- |
| [src/lifecycle/workflow.mjs](src/lifecycle/workflow.mjs) | Standalone state transitions and artifact-bound gates |
| [scripts/demo-lifecycle.mjs](scripts/demo-lifecycle.mjs) | Explicitly simulated lifecycle evidence |
| [src/cli.ts](src/cli.ts) | Running v1 commands, batch selection and error handling |
| [src/ingest/load.ts](src/ingest/load.ts) | Report normalization |
| [src/policy/engine.ts](src/policy/engine.ts) | Routing decisions and severity ordering |
| [src/state/store.ts](src/state/store.ts) | Local findings, run provenance and executor records |
| [src/remediator/agent.ts](src/remediator/agent.ts) | Cursor cloud execution, status and follow-up |
| [src/remediator/prompt.ts](src/remediator/prompt.ts) | Legacy scanner assumption and requested PR behavior |
| [src/verify.ts](src/verify.ts) | CI observation and its current readiness limits |

For the broader design, use the [architecture contracts](docs/prep/refactor-plan.md) and [pilot worksheet](docs/prep/pilot-worksheet.md). They describe work still to implement and evidence still to collect.

