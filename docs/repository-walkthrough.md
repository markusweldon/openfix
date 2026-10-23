# Walk through OpenFix

OpenFix explores a customer problem: security tools can find and enrich issues faster than teams can decide which evidence to trust, who should act, and whether a proposed change actually reduces risk. Its value hypothesis is less repeated investigation and more reviewable decisions across existing tools. Measure that hypothesis in a pilot; this repository establishes software behavior, not customer savings.

This is an optional 10–15 minute reading path. Open the files and diagrams together; no application, recording or live execution is needed. In a customer working session, first discover the problem, stakeholders, constraints and existing workflow, then choose the relevant stops.

## 1. Establish the scope

Open [the CLI](../src/openfix.mjs) and [input contracts](input-contracts.md). Follow the command surface from import and enrichment to validation, acceptance, patch verification and review.

**Explain:** “The unit of work is a persistent security case with evidence and a next decision. Finding import, investigation and permission to change software are separate operations.”

**Tradeoff:** explicit stages add friction, but make consequential actions inspectable. **Ask:** Where does work currently stall: validation, ownership, engineering acceptance or proving the fix?

## 2. Preserve what other tools already know

Read `upstreamClaims`, `caseKey` and `importObservations` in [import.mjs](../src/workflow/import.mjs). SARIF and GitHub observations about the same tenant lookup can share an investigation when repository, revision, asset, issue identity and location match. Original observations remain separate.

**Explain:** “An incoming finding may already contain reachability, validation and ownership evidence. Preserve it before deciding what needs more investigation.”

**Tradeoff:** conservative correlation misses some duplicates; it avoids silently treating different issues as one. **Ask:** Which tools already supply useful proof, and how do teams assess its authority?

## 3. Turn enrichment into an evidence plan

Read `factsFor`, `contextFact`, `assessCase` and `enrichCase` in [enrich.mjs](../src/workflow/enrich.mjs). Trace the tenant lookup’s owner, exposure and deployed revision. Evidence retains producer, subject, age and authority. Current disagreements remain conflicts; an old-revision claim remains visible without satisfying current context.

**Explain:** “Investigate the gaps that could change the decision. Reuse matching evidence with provenance, rather than automatically rerunning everything.”

**Tradeoff:** exact joins and expiration can pause work. The seven-day default needs customer policy. **Ask:** Which context sources are authoritative, and how quickly do they become stale?

## 4. Separate priority, acceptance and authority

Read `decideCase` and `recordCasePatch` in [operations.mjs](../src/workflow/operations.mjs), then the guards in [the lifecycle domain](../src/lifecycle/workflow.mjs). Suggested priority selects attention. Acceptance records owner, rationale, priority and current context. Changed or expired context requires acceptance again.

**Explain:** “High severity does not grant an agent permission to change a service. A human accepts the bounded work; the workflow checks its prerequisites.”

**Tradeoff:** this reference uses caller-supplied actor labels. Production requires authenticated identity and action authorization. **Ask:** Who can accept the risk and approve the change?

## 5. Explain proof through the tenant example

Read [validation.mjs](../src/workflow/validation.mjs), [tenant-probe.mjs](../src/workflow/tenant-probe.mjs) and `verifyCasePatch` in [operations.mjs](../src/workflow/operations.mjs). The narrow reference profile covers CWE-639 at `src/invoices.mjs:3`. Unsupported subjects remain inconclusive. Verification recomputes the committed diff digest and checks the exact changed head.

**Explain:** “Denying every invoice request blocks cross-tenant access but breaks the business function. Security and legitimate-access checks must both pass.”

**Tradeoff:** a narrow, inspectable check offers limited coverage. Other vulnerabilities need their own approved capability or reviewed external evidence. **Ask:** What behavior must a correct fix preserve?

## 6. Show where AI belongs

Read `taskPacket` in [operations.mjs](../src/workflow/operations.mjs), the [investigation skill](../.agents/skills/openfix-investigate/SKILL.md), and [providers.mjs](../src/workflow/providers.mjs). Packets carry the subject, evidence, gaps, permitted work and expected output. Finding text, code and tool output remain untrusted data.

**Explain:** “A capable model can help investigate and propose changes. The surrounding harness supplies durable state, evidence contracts, action boundaries and checks.”

**Tradeoff:** a packet is not a sandbox. Native Codex execution uses an approved external host; the optional Cursor bridge separately requires execution and draft-publication consent. **Ask:** Which host, data boundary and tool permissions can the customer approve?

## 7. Keep the decision inspectable

Read [store.mjs](../src/workflow/store.mjs) and [report.mjs](../src/workflow/report.mjs). Cases, evidence, unsuccessful attempts and decision history survive process restarts. The report is a read-only view of that store.

**Explain:** “The reviewer should see why the case moved forward, what failed, and which artifact was checked.”

**Tradeoff:** local atomic writes, locks and hash checkpoints help integrity; they are not signed audit storage or a multi-tenant service. **Ask:** What retention, access and audit requirements apply?

## 8. Read the negative cases

Open [workflow tests](../tests/workflow.test.mjs) and [lifecycle tests](../tests/lifecycle.test.mjs). Find stale context, conflicting owners, unrelated-profile validation, missing capability, failed legitimate behavior, self-review and changed-patch cases.

**Explain:** “The workflow must preserve uncertainty and refuse unsafe transitions. A returned PR, passing unrelated check or absent finding in a later scan is insufficient closure evidence.”

**Tradeoff:** these tests verify the harness; they do not measure model quality or broad vulnerability accuracy. **Ask:** Which failure paths would make the customer stop a pilot?

## Connect the architecture to the operating model

Use [the detailed architecture diagrams](architecture.md) and [AI security model](ai-security-model.md). OpenFix primarily supports securing conventional software **with AI**. Security **of AI agents** adds a separate evaluation track: hostile evidence, unsafe tool use, data disclosure and authorization failures. Promptfoo is a proposed evaluation option, not an installed integration.

Existing DevSecOps scanners, ownership, CI, review and deployment controls remain useful. AI adds adaptable investigation and change proposals; their evidence and authority still need checks. A focused pilot should measure analyst investigation time, reviewer time, accepted correct fixes, regression/rework rate, inconclusive cases and cost/latency against a baseline. Expansion is an operating decision supported by that evidence.
