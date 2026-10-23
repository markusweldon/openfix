# OpenFix: the next repository plan

## Recommendation

Evolve OpenFix into an **executable customer reference workflow for security investigation and controlled remediation**. Its useful contribution is connecting customer context, security capabilities, evidence, ownership, and authorized changes across existing systems.

The next increment should prove one customer workflow end to end. Broadening the workflow is valuable; building a new scanner, generic agent platform, cloud security product, and evaluation platform at once would obscure what the customer needs and what this repository actually contributes.

## What this prepares us to explain

A live customer exercise evaluates how a solution is discovered and adapted. A polished repository can illustrate that judgment, but the scenario and constraints must determine the recommendation. Start by asking whether the problem concerns vulnerable software, an unsafe AI application, an exposed deployment, or an investigation bottleneck. The same architecture is not automatically appropriate to all four.

Use the [exercise workbook](exercise-workbook.md) for rehearsal and the [product map](product-landscape.md) to select capabilities. The slides are optional reference material.

The implementation should make a customer engagement inspectable through a discovery brief, an evidence-backed security case, a bounded execution plan, exact-change verification and review, and a pilot recommendation with owners and measures. These are the useful outputs; the CLI, evidence store and agent executor support them. The first implementation increment must connect these outputs to the running application rather than add another disconnected simulation.

## Where the repository is today

| Surface | Implemented behavior | Limit |
| --- | --- | --- |
| `src/cli.ts` and npm `openfix` / `dev` | SARIF/JSON import, deterministic routing, Cursor remediation, PR CI observation | This remains the running application |
| `src/lifecycle/workflow.mjs` | Validation, acceptance, patch identity, verification, review, rollout and closure transitions | A separate in-memory domain prototype; caller-supplied evidence and identities |
| Lifecycle tests and demo | 16 software tests and a labeled simulation | No live scan, authenticated review, or deployment |
| Preparation pack | Deck, diagrams, workbook, research and plan | These describe current and proposed states explicitly |

The preparation materials and standalone lifecycle prototype are now on `main`. That makes them available on the default branch; it does not connect the lifecycle to the running CLI or complete a product refactor.

## The target customer workflow

1. **Understand and map.** Record the business problem, assets, repository and immutable revision, deployed version, system owner, trust boundaries, sensitive data, and constraints.
2. **Discover or import.** Use Codex Security where appropriate, and accept existing scanner/ticket inputs. Each observation retains its original producer and artifact; importing a report does not confirm it.
3. **Investigate and validate.** Establish the attacker-controlled input, reachable code path, failed control, prerequisites and supported impact. Record source-based and executed evidence separately. Preserve inconclusive results and coverage gaps.
4. **Assign ownership and priority.** Identify an accountable owner and explain business priority using severity, exposure, reachability, evidence quality and asset importance. A reviewer accepts a bounded remediation.
5. **Propose a controlled change.** Run in an isolated, reproducible environment with scoped tools and credentials. Produce an exact patch artifact and preserve execution outcomes.
6. **Verify and review.** Check the original issue, legitimate behavior and agreed regression checks against the exact changed revision. Failed, skipped or pending required checks remain incomplete. A changed patch invalidates previous verification and approval.
7. **Use normal change controls and retest.** Publish through a separate identity where required, review and merge normally, follow the customer's deployment process, and obtain post-change evidence before explicit closure.

OpenAI's Defense Factory describes a closely related continuous loop: inventory, discovery, dynamic validation, ownership assignment and verified remediation. The design above is this repository's implementation proposal, including explicit customer review gates. It is not a claim to reproduce OpenAI's internal implementation. [Official operating model and reference architecture](https://openai.com/the-defense-factory/).

## Build on products and preserve their boundaries

- **Codex Security:** use its code discovery, finding evidence and remediation workflows. Use native Cloud capabilities when they already solve the customer's problem. Choose a documented local CLI/SDK or supported export path for programmable integration; do not invent a Cloud API.
- **Customer cloud/runtime tooling:** provide asset, exposure, deployed-version and observation context through an explicit mapping. Uncertain mappings remain uncertain. Infrastructure mutations require their own authority and rollback path.
- **Promptfoo:** evaluate an AI application's or agent's behavior when that is part of the use case. For OpenFix itself, test hostile finding text, prompt injection, sensitive-data handling, tool misuse and approval bypass. This complements code-fix verification; it is a separate evidence contract.
- **Existing Cursor integration:** retain it as an optional remediation executor. Vendor-specific execution should sit behind a common job/patch contract instead of defining the whole application.
- **Endor Labs Agent Kit:** a useful public reference for reusable customer-task workflows, portable output contracts, evidence gaps and adapter boundaries. Its AI SAST contract separates finding verdicts, patch artifacts, approvals and action results. Learn that separation while using the customer's chosen security capabilities; an Endor integration is not implemented in OpenFix. [Repository](https://github.com/endorlabs/endor-labs-agent-kit), [portable AI SAST contract](https://github.com/endorlabs/endor-labs-agent-kit/blob/main/portable/ai-sast-remediation/output-contract.md).

## Keep, refactor, retire

| Keep | Refactor | Retire as a universal assumption |
| --- | --- | --- |
| SARIF/JSON normalizers | Finding row into a customer security case | Every workflow starts with SARIF |
| Provenance and run IDs | Revision-aware observations and recurrence | A missing result in a later scan means fixed |
| Explainable policy | Separate priority, acceptance and execution authority | Severity alone chooses the next action |
| Durable executor tracking | Provider interface and evidence manifests | Cursor is the whole control plane |
| Human merge boundary | Artifact-bound review and closure | Agent completion or a PR URL proves remediation |

## First address existing assurance gaps

These observed code behaviors remain implementation work; the documentation and standalone prototype do not fix them:

- `src/verify.ts:281–283` returns zero for skipped and pending verification. Introduce explicit passed, failed and incomplete outcomes, with a non-success readiness result for missing required proof.
- `src/remediator/prompt.ts:19,37–43` requires detection to originate from an external deterministic scanner. Replace that with producer-specific provenance and verification appropriate to the finding.
- `src/policy/engine.ts` falls back to defaults after invalid configuration and ranks eligible work mainly by severity. Surface configuration errors and make prioritization explainable from customer context.
- `src/state/store.ts` turns unreadable or corrupt state into a new empty state and deduplicates started/finished fingerprints without full revision/recurrence context. Preserve evidence, distinguish first-run absence from corruption, and use atomic versioned persistence.
- `src/cli.ts` selects one capped batch for `--all-auto`; it does not continue through the rest of the queue. Make the option's behavior explicit before using it as a queue-draining service.
- The new lifecycle module checks role labels supplied by its caller. Operational authorization needs authenticated actors and trusted evidence ingestion; these local assertions are not enterprise RBAC.

## Implementation increments and acceptance criteria

### 1. Make the lifecycle the running application's record

Use one typed case domain and migrate the standalone prototype into it. Store a customer brief with the problem, stakeholders, goals, approved scope, data/action constraints and baseline alongside the case. Add versioned persistence and CLI commands to inspect the brief, record validation, assign an owner, accept/defer/dismiss, and inspect evidence. SARIF creates a candidate observation inside a case. Keep v1 data readable through an explicit migration or adapter.

**Acceptance:** the actual CLI operates on persistent cases and shows the customer problem, constraints, owner and next decision. Corrupt state and invalid policy produce errors. Restarting preserves evidence and decisions. A changed scope or data constraint can be recorded and reflected in the next action. A candidate cannot silently become confirmed or authorized because its imported payload says so.

### 2. Wire one real Codex Security path

Choose the documented CLI/SDK or native Cloud workflow that fits the customer's execution and data requirements. Preserve source revision, producer/version, scan completion, reviewed/deferred surfaces, finding evidence, validation method and failure status. Keep results outside the scanned worktree and handle access/cost limits explicitly.

**Acceptance:** one real finding can be traced back to its original artifacts. A failed runtime or policy exit is handled according to the documented contract. A completed scan with coverage gaps is displayed accurately. A later scan's absence does not auto-close an older issue.

### 3. Complete one controlled remediation

Use a disposable environment, bounded changes, an executor adapter and a patch manifest. Run agreed verification outside the author's writable evidence. Bind review and readiness to the exact artifact and changed revision. Observe real CI checks rather than scanner stubs.

**Acceptance:** demonstrate one accepted fix, one failed or incomplete verification, and approval invalidation after a changed patch. No production credential is available to the patch author. Missing checks cannot establish readiness.

### 4. Add customer context and a workbench

Connect one approved asset/owner/version data source before adding many vendor integrations. Show the actual case state, evidence, ownership, uncertainty and next decision. Make the interface useful for an engineer and a security reviewer.

**Acceptance:** explicit asset/version joins can be inspected. Missing or conflicting mapping blocks claims that depend on it. The interface reads operational state and artifacts rather than a fabricated success dashboard.

### 5. Evaluate and expand deliberately

Create labeled positive, negative and inconclusive cases. Add a Promptfoo-backed agent evaluation lane when the use case warrants it. Use tool traces and deterministic checks for authorization and scope, alongside appropriate human review. Measure investigator/reviewer effort, accepted fixes, false fixes, latency and total attempted-run cost.

**Acceptance:** failures and retries remain in denominators. Evaluation covers malicious evidence, unauthorized actions, data leakage, refusal/abstention, regression and timeouts. Expansion requires agreed customer evidence and a tested operating/rollback process.

## Focus before the customer exercise

1. Learn the native Codex Security finding/evidence/patch experience using the Pro access provided for familiarization. Confirm the specific surface and its billing before starting a run.
2. Practice discovery and product selection using the workbook, including a constraint that forces a different design.
3. Explain one workflow, its boundaries, proof requirements and pilot decision without relying on slides or a running demo.
4. Know the repository's real status and the next implementation increment. Do not spend the remaining preparation window pretending the full platform has been built.

The recommendation is to keep **OpenFix** as the project name and make its purpose clearer: **customer context to verified security changes**. Prove a useful operating workflow, then expand its integrations and autonomy from measured evidence.
