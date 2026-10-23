# OpenFix architecture contracts and implementation status

The initial refactor is implemented in version 0.2. Read [architecture](../architecture.md) for the current system and [repo strategy](repo-strategy.md) for remaining increments.

## Running code

| Concern | Runtime implementation |
| --- | --- |
| Default CLI | `src/openfix.mjs` with import, enrich, show/list, validate, decide, plan, patch, verify, review, rollout/close, report and serve |
| Source adapters | `src/workflow/import.mjs` preserves producer observations and supplied evidence, with scoped correlation |
| Evidence and priority | `src/workflow/enrich.mjs` checks source/revision/freshness, joins context, records conflicts and explains priority |
| Lifecycle | `src/lifecycle/workflow.mjs` is used by `src/workflow/operations.mjs` on persistent cases |
| Persistence | `src/workflow/store.mjs` uses cross-process writer exclusion, atomic/fsynced writes and integrity checkpoints |
| Validation | `src/workflow/validation.mjs` executes the reference probe or records explicitly reviewed external evidence |
| Optional executor | `src/workflow/providers.mjs` and `cursor-bridge.ts` gate the existing Cursor SDK path behind an accepted case |
| Native workflow | Exported task packet and repository investigation/remediation skills use the customer's approved existing host |
| Review surface | `src/workflow/report.mjs` renders current state to an interactive HTML casebook or loopback-only read-only server |

## Important distinctions

- Producer enrichment is preserved, not upgraded to trusted independent evidence.
- Matching observations are grouped for investigation, not silently treated as proven duplicates.
- Source-supported findings and runtime reproduction use distinct methods and limits.
- Priority selects attention; acceptance and execution authority remain separate.
- An exact patch, passing checks, human review, deployment and closure are different states.
- Rollout/closure currently record operator attestations; they do not perform or independently observe production changes.

The old Cursor CLI is available through `npm run legacy -- ...`. Its invalid policy and corrupt state now fail explicitly, its source-agnostic prompt carries bounded case evidence, and incomplete CI observation returns a non-success readiness code. It is not the default application or independent fix verifier.

## Boundaries still requiring production work

Local actor labels are not authenticated RBAC, local audit hashes are not administrator-proof signatures, and the bounded reference process is not an isolated customer-code worker. Live product/provider checks, authenticated context connectors and external deployment verification remain to be qualified. These limits are part of the operating design and are not hidden by a successful fixture run.
