# Customer discovery and pilot worksheet

Original hypothetical scenario: a multi-tenant billing service has security findings from code review and scanners, cloud exposure metadata, and runtime observations. The team wants to reduce investigation and remediation effort while keeping evidence and review quality.

The [integrated OpenFix demo](../../DEMO.md) exercises this type of workflow with synthetic reports and actual reference-code checks. Use it to inspect evidence and failure branches; customer targets and baselines still need discovery.

## Discovery before architecture

| Explore | Ask | Architectural consequence |
| --- | --- | --- |
| Business outcome | Where does the current process lose the most time? What would improve for customers? | Optimize the actual bottleneck, not just patch generation |
| Scope and owners | Which application, vulnerability class, security owner, and service owner? | A bounded pilot and an accountable reviewer |
| Finding quality | What fraction is actionable? What evidence do reviewers trust? | Labeled baseline and explicit validation standards |
| Asset identity | How do findings map to repository, commit, cloud resource, and deployed version? | Join only supported identities; preserve mapping gaps |
| Data | Can source, logs, or sensitive fields leave the environment? What retention and residency apply? | Choose the execution environment and minimize data |
| Identity and authority | Who may read code, run a reproducer, create a patch, publish, merge, or deploy? | Separate credentials and approval boundaries |
| Verification | Which regression, exploit, legitimate-behavior, scanner, and CI checks matter? | Define evidence before the model runs |
| Rollout | What must be true to expand, and what stops the pilot? | Explicit expansion and rollback decisions |

## Agree the first pilot

One service and one issue class, a small approved data set, isolated execution, and human-reviewed patch artifacts or draft PRs. Include negative cases and failed runs. No autonomous infrastructure changes or merges.

| Stage | Deliverable | Decision owner |
| --- | --- | --- |
| Baseline | Approved data flow, threat model, labeled examples, current effort and cycle time | Security + service owner |
| Prototype | Evidence-supported findings, reproduction where feasible, controlled patches, recorded failures and proof gaps | Implementation engineer |
| Evaluate | Independent verification, reviewer assessment, cost and effort comparison | Security reviewer |
| Decide | Expand one scope dimension, revise, or stop | Customer sponsor + security owner |

## Define measures without inventing results

- **Accepted fix rate:** independently verified, reviewer-accepted remediations / attempted accepted findings. Include failed attempts.
- **False-fix rate:** proposed fixes rejected on security or regression grounds / proposed fixes.
- **Human effort:** investigation plus review minutes per accepted fix, compared with the same issue class before the pilot.
- **Elapsed time:** acceptance of a finding to reviewer acceptance of the verified patch; show median, tail, and sample size.
- **Evidence completeness:** runs containing the source finding, immutable revision, patch identity, verification results, and limitations / attempted runs.
- **Boundary violations:** unauthorized scope, data, or action changes. Any completed violation stops expansion.
- **Cost per accepted fix:** execution and review cost, including failed and repeated runs / accepted fixes.

Agree targets after measuring the baseline. A deterministic fixture tests software behavior; it does not establish model quality or production ROI.

## Practice responding to new constraints

If the customer cannot share source, revisit a documented execution option and its data flow. If a runtime log cannot be tied to the deployed revision, keep it as uncertain context. If a candidate lacks evidence, investigate or defer it. If verification is incomplete, keep the proof gap open. If the patch changes, invalidate approval and verify the new artifact.

## Rehearsal rhythm

For a one-hour customer exercise, practice spending roughly the first 10 minutes on discovery, the next 10 on scope and assumptions, 15 on architecture and tradeoffs, 15 on evidence and rollout, and the final 10 on unresolved questions and a recommendation. This is a personal pacing aid, not a prediction of an interview's agenda.
