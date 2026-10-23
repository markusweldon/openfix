# OpenFix roadmap

OpenFix 0.2 makes multi-source investigation and controlled remediation the primary runtime. The original Cursor SDK pipeline is an optional executor, and the lifecycle now operates on persistent cases.

## Delivered in 0.2

- Import SARIF, GitHub alerts, Snyk JSON, native Codex Security scan JSON and source-neutral envelopes.
- Preserve upstream enrichment, original observations, scope, freshness, authority and input digests.
- Correlate scoped observations, enrich exact asset/source context, expose evidence gaps and conflicts, and explain business priority.
- Execute the tenant-boundary reference profile, retain inconclusive attempts, accept scoped work, bind real patches, independently verify and review.
- Persist evidence and decisions atomically with a cross-process writer lock and integrity checkpoints.
- Export native-agent packets and repository skills; retain an optional gated Cursor dispatch bridge.
- Produce the interactive workbench, recorded demo, diagrams and visual reference deck.

## Next: qualify a real customer pilot

1. **Isolated execution.** Implement a worker adapter with ephemeral environments, restricted network, credential separation, resource limits and externally retained evidence. The local reference runner is not that boundary.
2. **Trusted identity and evidence.** Authenticate actors and tenants, enforce RBAC and scope at every tool boundary, verify artifact origin and preserve audit outside the author's writable environment.
3. **Native product round trip.** Qualify a real Codex Security scan/validation/fix export path using documented authentication, scope, runtime and billing contracts. File-shape support is implemented; a live product run is not claimed.
4. **Operational context and closure.** Add one authenticated asset/owner/version connector and one deployment-verification path. Assignment, acceptance, merge and deployment remain distinct evidence states.
5. **Measured expansion.** Establish a customer baseline, representative positive/negative/inconclusive cases, agent-behavior evaluations where useful, and explicit expansion/stop decisions.

See [architecture](docs/architecture.md), [contracts](docs/input-contracts.md), [walkthrough](DEMO.md) and [verification](docs/prep/validation.md). Start customer discussions with the [exercise workbook](docs/prep/exercise-workbook.md); the provided live exercise requires no slides or advance implementation.
