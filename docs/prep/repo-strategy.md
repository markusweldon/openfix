# OpenFix: implemented workflow and next increments

OpenFix 0.2 makes findings intelligence and controlled remediation the primary application. The [README](../../README.md), [architecture](../architecture.md) and [walkthrough](../../DEMO.md) describe the runnable implementation.

## What changed

The original application imported scanner findings, routed them through policy and launched Cursor agents. The default CLI now persists customer cases, original source observations, enrichment, validation runs, owner/priority decisions, patch identities, verification and review. The existing lifecycle module is integrated into that runtime. Cursor remains an optional execution provider.

## Customer outputs supported now

| Output | Implemented mechanism |
| --- | --- |
| Customer problem and scope | Brief attached at import, retained in the case and exported task packet |
| Attributed findings | SARIF, GitHub, Snyk, Codex Security scan JSON and OpenFix envelope adapters; original observations, scope and artifact digests |
| Evidence-quality assessment | Freshness, per-evidence revision, authority labels, exact context joins, conflict/gap and reuse plans |
| Security judgment | Explicit validation methods/outcomes; one executable tenant-boundary profile; reviewed external attestations; failed attempts retained |
| Practical execution plan | Owner/priority acceptance with a context digest; bounded native-agent packet; optional gated Cursor dispatch |
| Fix evidence and review | Actual Git diff/head identity, security and legitimate-behavior checks, changed-patch invalidation and different-actor review gates |
| Customer recommendation | Read-only workbench with evidence, unsuccessful attempts, next decision and explainable priority; pilot measures remain to be agreed with a real customer |

## Evidence from the integrated demo

Five synthetic source observations become four cases. Four reference probes actually execute and one unavailable-profile attempt stays inconclusive. A vulnerable lookup is confirmed, an already protected lookup is disproved, and conflicting owner context remains visible. A deny-all patch fails the legitimate-behavior check before the corrected patch passes and receives artifact-bound review. No model, live scanner or deployment result is claimed.

This is useful software evidence; it is not a detection-accuracy benchmark, production authorization system or customer ROI result.

## Alignment with public workflows

[Defense Factory](https://openai.com/the-defense-factory/) combines inventory, discovery/import, dynamic validation, ownership and verified remediation. OpenFix preserves this separation while starting with a bounded local reference implementation. Imported findings may already have useful enrichment; review their scope and proof before repeating work or adopting their verdict.

[Codex Security](https://learn.chatgpt.com/docs/security/cli/reference) supplies native security workflows and exports. OpenFix imports the documented scan JSON/SARIF paths and exports agent-ready cases. A completed producer scan does not establish complete coverage, and absence in a later report does not close a case.

[Endor Labs Agent Kit](https://github.com/endorlabs/endor-labs-agent-kit) is a reference for customer-task workflows, portable contracts and evidence/adapter boundaries. OpenFix's repository skills and task packets make those boundaries explicit without assuming an Endor backend.

[Promptfoo](https://www.promptfoo.dev/docs/red-team/agents/) can evaluate the agent's actions, injection resistance and data handling. That future lane is distinct from proving that a source-code patch addresses a vulnerability.

## Next increments and acceptance criteria

1. **Qualify isolated workers.** Provision ephemeral execution with approved data, network, credentials and resource bounds. Acceptance: untrusted customer code cannot access control-plane credentials or edit independent evidence; cancellation and runtime failure remain inspectable. The current local reference process is not this boundary.
2. **Authenticate actors and evidence.** Replace caller-provided names with identities and tenant/repository/action authorization. Acceptance: attempts to forge actor roles, evidence origin or approval fail at the tool boundary, with audit outside the author's writable store.
3. **Complete one live native-product round trip.** Use documented account access, authentication, scan scope, export, validation and patch contracts. Acceptance: actual product findings and fix artifacts reach a case with correct producer/version, coverage, cost and error evidence. File adapter support alone is not that live check.
4. **Connect one operational context source and deployment check.** Acceptance: asset/owner/version joins can be inspected; ambiguous mappings remain gaps; production closure requires actual post-change evidence.
5. **Measure and expand.** Establish an approved customer baseline and labeled positive/negative/inconclusive cases. Include retries, failures, reviewer effort and total cost. Expand one scope dimension only after an agreed operating decision.

For the live customer exercise, start with [discovery and adaptation](exercise-workbook.md). The repository illustrates a working design; the customer's actual problem and constraints determine whether to use this workflow, a native capability or a smaller integration.
