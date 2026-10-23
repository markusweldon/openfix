# OpenFix

**Customer context to verified security changes.** OpenFix is a reference project for investigating a customer's security problem, designing a practical AI-assisted workflow, and deciding whether a controlled pilot produces useful, trustworthy results.

The design starts with the customer: where does work get stuck, which evidence is available, who owns the decision, and what would justify a change? Finding a vulnerability, generating a patch, and establishing that the customer should deploy it are separate decisions.

## The customer workflow

The target workflow makes these decisions inspectable:

| Customer decision | Evidence and output |
| --- | --- |
| **Discover the problem** | Business consequence, stakeholders, current workflow, constraints, approved scope and a measurable outcome |
| **Investigate the security issue** | Finding provenance, source revision, attacker control, failed control, supported impact, and relevant asset/runtime context with mapping gaps visible |
| **Prioritize the next action** | Accountable owner, exposure and business importance, evidence quality, and a reason to investigate, remediate, defer or dismiss |
| **Design and bound execution** | Choice of native product or integration, model/tool responsibilities, data flow, scoped identities, isolated execution and human decision points |
| **Verify and review the change** | Exact patch and revision, original-issue evidence, legitimate behavior, regression checks, uncertainty and reviewer disposition |
| **Decide whether to roll out** | Pilot milestones, baseline, accepted outcomes, review effort, cost, stop conditions, deployment controls and rollback owner |
| **Explain and adapt** | A concise customer recommendation, practitioner evidence, assumptions that changed, open questions, next owner and next decision |

The same engagement can end with an accepted patch, a deferred investigation, a recommendation to use an existing product, or a decision to stop. A useful result depends on the customer's problem and evidence.

## One bounded case to prove

Use the original, hypothetical billing-service case to connect these decisions: a possible cross-tenant lookup issue, an identified service owner, source and deployed-version evidence, a bounded remediation, and security plus legitimate-behavior checks. Exercise an inconclusive investigation and a patch that breaks legitimate use as well as a successful result. The [pilot worksheet](docs/prep/pilot-worksheet.md) defines the evidence and measures; the [repo plan](docs/prep/repo-strategy.md) defines the implementation work.

This is the proposed integrated workflow. The existing CLI, standalone domain prototype and runnable instructions are described below under [implementation status](#implementation-status).

## Start here

- [Prioritized repository plan](docs/prep/repo-strategy.md): what to keep, refactor and implement next, with acceptance criteria.
- [Customer working-session workbook](docs/prep/exercise-workbook.md): discovery, secure architecture, evaluation, pilot decisions and adaptation.
- [Product map](docs/prep/product-landscape.md): Defense Factory, Daybreak, Codex Security, Promptfoo, access and billing boundaries.
- [Preparation assets](docs/prep/README.md): editable Excalidraw and PowerPoint, PDF, diagrams and source links.
- [Runnable walkthroughs](DEMO.md): the lifecycle simulation and the separate live Cursor CLI.

The supplied customer exercise requires no presentation or advance implementation. These materials support rehearsal and discussion; the scenario should determine the design.

![Proposed OpenFix security lifecycle](docs/prep/diagrams/lifecycle.svg)

*Target workflow. Implementation status is recorded separately below.*

## Run the lifecycle prototype

Use Node.js 22.13 or later. From the repository root:

```bash
npm install
npm run test:lifecycle
npm run demo:lifecycle
```

The demo uses fabricated actors, revisions, evidence and results to exercise the decision sequence. It makes no model or scanner calls and performs no merge or deployment. The tests check software gates, including missing evidence, stale verification and approval invalidation; they do not establish model quality or production readiness.

## Run the v1 CLI

The CLI accepts SARIF and OpenFix findings JSON, merges inputs by fingerprint, applies [policy.yaml](policy.yaml), and sends eligible findings to [Cursor cloud agents](https://cursor.com/docs/sdk/typescript). Its prompt requests draft fix PRs and human review. Merge and deployment authority remain with the customer's repository controls.

Ingest and triage run locally without a cloud credential:

```bash
npm run openfix -- ingest fixtures/findings/demo.sarif
npm run openfix -- triage
```

For live remediation, configure `.env` using [.env.example](.env.example): `CURSOR_API_KEY`, `OPENFIX_TARGET_REPO`, and the actual scanned revision in `OPENFIX_COMMIT_SHA`. Then ingest the report for that repository and revision. Re-ingest after changing target context: remediation prefers the context stored at ingest time. Fixture ingestion alone does not establish a report/revision match. ChatGPT Pro does not supply a Cursor API credential.

These commands use Cursor cloud and can create or update remote PRs:

```bash
npm run openfix -- remediate
npm run openfix -- status --last
npm run openfix -- resume --last --prompt "Address the review feedback and update the regression test."
```

Observe a resulting PR's CI through an authenticated GitHub CLI (`gh`):

```bash
npm run openfix -- verify --last
npm run openfix -- verify --pr https://github.com/OWNER/REPO/pull/NUMBER --checklist
```

| Command | Current behavior |
| --- | --- |
| `ingest <path> [path…]` | Normalize SARIF/JSON, deduplicate fingerprints and store run context under `.openfix/` |
| `ingest --from simulated:semgrep` | Load a simulated adapter response; no live MCP integration |
| `triage` | Explain `auto_fix`, `human_only` and `suppress_noise` policy decisions |
| `remediate` | Start one eligible Cursor job; `--agents N` selects a concurrent batch, capped by `OPENFIX_MAX_CONCURRENT` |
| `remediate --fingerprint <fp>` | Select one eligible finding |
| `remediate --all-auto` | Start a batch up to the concurrency cap; the current implementation does not loop through the remaining queue |
| `status <agentId>` / `status --last` | Inspect a durable Cursor agent |
| `resume <agentId> --prompt "…"` | Send a follow-up turn; also supports `--last` |
| `verify --pr <url>` / `verify --last` | Observe PR check status; `--checklist` also prints review guidance |

Use `--verbose` with `remediate` for the full agent stream. The default board shows progress and a final summary with each agent ID and PR URL. Remediation exits nonzero if a job throws, does not finish successfully, or finishes without a PR URL.

## Implementation status

The running application still uses the original remediation path. The next functional increment is to connect customer context, persistent cases, evidence and decisions to that runtime. Reorganizing this README does not complete that integration.

| Surface | What works today | Boundary |
| --- | --- | --- |
| [v1 CLI](src/cli.ts) | SARIF/JSON import, policy routing, Cursor cloud remediation, agent status/resume, PR CI observation | Imports reports; does not independently validate findings or prove a fix |
| [Lifecycle prototype](src/lifecycle/workflow.mjs) | In-memory validation, acceptance, patch identity, verification, review, rollout, revalidation and closure gates | Standalone model with caller-supplied evidence and identities; not wired into the CLI |
| [Preparation pack](docs/prep/README.md) | Workbook, research, editable whiteboard, purple-gradient deck, diagrams and implementation plan | Reference material; Codex Security integrations, operational context and production controls remain proposed |

## Configuration and current limits

- `OPENFIX_MAX_CONCURRENT` defaults to 2; `OPENFIX_MODEL` defaults to `composer-2.5`. At ingest, target repository and revision default to `GITHUB_REPOSITORY` and `GITHUB_SHA` in Actions; explicit `OPENFIX_*` values override those defaults. Remediation prefers the stored scan commit, then the stored ref. Without a known commit, the agent can start from a mutable ref; record and check the source snapshot before relying on a result.
- Policy routes critical findings, secrets, IaC and sensitive paths toward human handling after noise/duplicate checks. Eligible work is ordered mainly by severity. This is routing, not finding validation, business prioritization or authenticated remediation approval.
- `verify` observes CI. It has no required-check allowlist and returns zero for pending or unavailable results; skipped/neutral checks are not proof. A green result does not establish security verification or merge readiness. The companion demo application's scanner job is a stub.
- The [remediation Action](.github/workflows/openfix-remediate.yml) is manually triggered with `workflow_dispatch`. A reusable workflow, automatic scanner hook and published Action are future packaging options.
- State is local JSON under `.openfix/`; production persistence, recurrence tracking, trusted evidence, authenticated review, isolated execution controls and rollout integration require implementation. Keep `.env` and `.openfix/` out of version control.

The v1 prompt assumes detection comes from an external deterministic scanner. That is a legacy adapter assumption. The [next design](docs/prep/refactor-plan.md) supports AI-assisted discovery and other producers while keeping provenance, independent verification and explicit authority.

See the [roadmap](ROADMAP.md) for the next increment and [verification record](docs/prep/validation.md) for checks performed and their limits.

## License

MIT

