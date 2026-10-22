# OpenFix talk track

This is an original rehearsal aid and independent architecture proposal. Start with discovery and use only the visuals that help.

## 01. From security signals to reviewed, verified change

Open with the customer outcome. Explain that this is an independent project, with a tested lifecycle prototype and a proposed integration architecture. Ask permission to use a visual only if useful; a discovery conversation does not need a full presentation.

## 02. Start with the customer outcome

Ask what hurts and who owns the workflow before discussing products. Establish current effort and remediation time. The billing scenario is invented for practice and should never be presented as the actual customer scenario. Avoid invented ROI numbers.

## 03. The complete security loop

Describe the workflow as a design rather than a rigid OpenAI product sequence. Establish threat context, discover or import candidates, validate, and obtain acceptance before remediation. Early triage can select expensive investigations. Verify the exact patch, review it, use normal merge and deployment controls, then revalidate and close explicitly. Negative and uncertain outcomes are first-class states.

## 04. Keep these decisions separate

Confidence is separate from severity and business priority. A scanner result or model claim is a candidate until evidence supports it. An accepted finding is a human prioritization and scope decision. Patch creation does not establish verification. Verification does not automatically close a finding.

## 05. From a signal to an attack path

Walk through source, failed control, sink, and supported impact. Explain which evidence is executed and which is source-based. Cloud exposure alone is not a vulnerability, and runtime logs must map to the relevant asset and version. Preserve ambiguity rather than escalating a claim beyond its evidence.

## 06. A control plane with clear authority

OpenFix owns the lifecycle policy and evidence record. Codex Security can supply discovery and validation; existing scanners remain useful inputs. Cloud and runtime systems contribute approved context. An isolated executor proposes a bounded patch. Verification, human review, and publication use separate authority. This is the target architecture, not a statement that these integrations are all implemented.

## 07. A useful workflow handles uncertainty

A false positive or incomplete validation is a useful output. Source-based analysis can support a finding without runtime reproduction, but execution-dependent uncertainty must remain open. A completed scan can have deferred surfaces and coverage gaps; completion and completeness are different measures.

## 08. One finding, all the way to review

Run node scripts/demo-lifecycle.mjs and node --test --test-isolation=none tests/lifecycle.test.mjs. The demo uses explicit simulated evidence. The tests exercise the actual state gates, including stale verification and changed patch approval. Do not describe this as a live scan, an executed exploit, or a production rollout.

## 09. Controls travel with the workflow

Distinguish a local command sandbox from isolated execution of arbitrary customer code. Discuss least privilege, data handling, egress, immutable verification inputs, cancellation, auditability, and rollback in terms of the actual customer constraints. Actor labels in the prototype are caller assertions, not authenticated enterprise RBAC.

## 10. A small pilot with a real decision

Propose a bounded pilot rather than broad autonomous rollout. Include a false positive, missing context, a broken build, a patch that denies all legitimate requests, and a timeout. Agree numerical targets after measuring the baseline. Report sample size and failed attempts; avoid treating replay quality as model quality.

## 11. What exists, and what changes

Be candid about what is real. The original code is a useful remediation adapter. The new lifecycle domain and its tests are executable. The complete production integration and workbench are proposed, not delivered. Explain the migration in stages rather than implying that a diagram proves functionality.

## 12. Use Pro to learn the workflow

A separate API key is not necessary to learn Codex with ChatGPT sign-in. ChatGPT subscription access and API billing are different paths. Do not assume Pro is a production service architecture or unlimited scan entitlement. The attempted local live Codex run was blocked by read-only runtime state; no live result is claimed.

## 13. Leave with a concrete recommendation

Summarize your assumptions and the customer decision you recommend. State the inputs you need, the owner, the expected evidence, the open limitations, and the next decision date. Invite correction. Adapt the proposed workflow to the customer rather than forcing every use case into a prebuilt pipeline.

## 14. Sources and practical boundaries

Use the linked public documentation as the current contract. This deck contains no confidential recruiter messages, customer data, inferred internal roadmaps, or reconstructed interview questions. It is a rehearsal and architecture aid, not a required presentation or evidence of a deployed service.
