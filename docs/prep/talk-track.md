# OpenFix talk track

OpenFix 0.2 repository walkthrough and implementation reference. Use the code, tests and diagrams to explain value and tradeoffs. This optional companion does not require running the application or a live AI service.

## 01. Evidence to action.

Use this as an optional companion while reading the repository and explaining its value. The default CLI persists cases, imports evidence, assesses context, validates supported cases, records acceptance, binds a committed diff, verifies it and records human review. The code and tests include synthetic reports and trusted local fixture checks. There is no live AI execution claim, live scanner integration, merge or deployment to show. The interview is a collaborative working session that requires no prepared presentation. Follow the customer scenario and use a relevant file or diagram only if it helps.

## 02. What AI adds to a mature security workflow

Mature DevSecOps already includes investigation, correlation, risk assessment, automation, testing and human review. The opportunity for AI is flexible reasoning across unfamiliar code and evidence, generating hypotheses, selecting useful follow-up work and proposing changes with less bespoke glue. Those benefits are hypotheses to measure, not properties proven by these fixtures. OpenFix implements the context and decision substrate: preserve what tools already know, expose missing or conflicting evidence, constrain a proposed action and independently verify the exact change. Its portable packets and optional executor can host an AI contribution, but the repository does not currently execute an OpenAI model. Explain value through code boundaries, tests and tradeoffs rather than promising autonomy or replacing CI.

## 03. Many observations, one persistent case

Adapters import local SARIF, GitHub code-scanning exports, Snyk JSON and supported Codex Security scan JSON, along with a generic finding envelope. These are file adapters, not live service connectors. Original observations remain linked to artifact digests and source identity. Correlation is deterministic and conservative; it is not a universal semantic deduplication engine. The local store uses atomic replacement, a writer lock and a hash-chained event audit with a state checkpoint. These mechanisms do not provide authenticated multi-tenant storage or an external tamper-proof ledger.

## 04. Reuse evidence and preserve its authority

Evidence records preserve upstream assertions separately from local evidence and explicit reviewed adoption of external validation. Context joins require the exact repository, asset and revision. Subject-mismatched evidence cannot silently change current context. The default freshness window is seven days, with explicit expiry supported; missing dates remain unknown and future timestamps are flagged. The freshest record per origin, producer and kind contributes to current assessment. Fresh contradictions remain visible instead of being overwritten by source precedence. The plan can reuse with provenance, refresh or verify, collect, resolve a conflict, or review upstream validation. A new or expired context record invalidates accepted scope where required.

## 05. The implemented local architecture

This diagram describes the implemented local architecture. The default src/openfix.mjs CLI calls the workflow modules and persistent store. File adapters supply findings and context, and a customer brief records goals and boundaries. The same stored cases feed assessment, the read-only HTML workbench and agent task packets. The built-in tenant-isolation profile runs trusted local fixture code only after explicit execution authorization. Its supported subject is CWE-639 at src/invoices.mjs:3; mismatched findings remain inconclusive. Optional Cursor dispatch calls the retained executor bridge. Neither local child-process bounds nor named actor labels are a production isolation or identity boundary. The repository imports supported scan output; it does not invoke a live Codex Security scan.

## 06. Each case carries evidence and decisions

The path is implemented through the default CLI. Imported evidence is assessed before additional investigation. Validation can confirm, disprove or remain inconclusive. Acceptance records owner, priority, rationale and context. A committed diff is then recorded with exact base, head and digest. A different actor runs the approved verification profile and a reviewer approves the exact patch hash. New context or a replacement patch can invalidate earlier decisions. Review does not merge or deploy. Rollout and closure commands require separate change records, exact deployed revision and post-change evidence; the local reference example stops at approved_for_change.

## 07. A repository map for the conversation

Start at src/openfix.mjs for the CLI boundary and src/workflow/store.mjs for persistence. Then follow import.mjs to enrich.mjs to operations.mjs and the lifecycle state machine. The file links open the public repository. Read the tests alongside the implementation: tests/workflow.test.mjs covers workflow behavior, while tests/lifecycle.test.mjs concentrates on decision invariants. src/workflow/report.mjs is the read-only report surface. operations.mjs exports task packets; providers.mjs describes adapters and optional Cursor dispatch. The useful conversation is why these boundaries exist, which customer problem they address and where implementation limits remain. No application or model needs to run during the walkthrough.

## 08. Read the example as four distinct decisions

The synthetic reports produce five observations and four correlated cases. The tenant-isolation profile executes four times: vulnerable baseline, protected baseline, deliberately broken patch and corrected patch. The dependency profile is unavailable, creating a fifth attempted check with an incomplete outcome, not a successful reproduction. The protected case is disproved and dismissed. The cloud owner contradiction remains unresolved. Report the denominator honestly: these reference checks demonstrate workflow mechanics and negative cases, not model performance, generalized vulnerability coverage or a customer ROI result.

## 09. A false fix reveals the verification contract

The reference fixture initially returns another tenant invoice. The first committed patch denies every request. It blocks the attacker but also breaks the legitimate owning tenant, so regression verification fails and the workflow rejects an approval attempt. The corrected committed patch adds the tenant predicate and preserves the legitimate lookup. Both checks pass and the reviewer approves that exact hash. The reference code edit is deterministic; it provides a testable example rather than evidence of model-generated remediation. This is evidence of an important evaluation property: security-only success cannot justify a broken product.

## 10. Approval belongs to an exact change

Patch recording binds a real git diff from the recorded base to a committed head, hashes the binary diff and rejects more than twenty changed files. Verification checks the repository snapshot, exact head and digest before executing the selected profile. The reference verifier permits only invoice-file changes; changes beyond that surface remain incomplete. Missing prerequisites or an artifact mismatch produce an incomplete result rather than success. A local verifier label must differ from the author label. Review requires passing independent verification and the exact patch hash. Labels are audit assertions supplied by the operator, not authenticated identities or a separation-of-duties enforcement boundary. Merge, deployment and post-change closure remain separate decisions.

## 11. Give agents a bounded security case

The agent packet carries the case subject, customer brief, observations, current evidence, gaps, action boundary and expected output contract. Instructions distinguish producer assertions, source analysis and runtime proof, and treat code comments, finding text and tool results as data rather than instructions. Packets are handoff artifacts; they do not themselves invoke an OpenAI model. The repository includes .agents skills for case investigation and patch verification. Optional Cursor dispatch reuses the existing executor, requires accepted scope, --execute, --publish-draft and a named --actor, and is separate from the local reference checks. Returned PRs still need exact-patch import, verification and review.

## 12. Use native security capabilities

This alignment uses public descriptions, not a claim about internal OpenAI architecture or an official integration. Start with native Codex Security functionality and use the documented contract of the customer environment. OpenFix imports supported Codex scan JSON; live scanning is outside the implemented local path. Defense Factory describes a continuous operating approach, and Daybreak encompasses a wider stack. Promptfoo helps evaluate AI applications and adversarial agent behavior; it is relevant when a model-driven step exists. Promptfoo execution is not implemented in the repository. ChatGPT Pro familiarization does not establish that every Cloud scan is included; confirm product access and billing separately.

## 13. What remains for production

The trusted local reference profile is a bounded child process, not a container, VM or network sandbox for arbitrary customer code. Actor labels do not establish authentication, RBAC or enterprise separation of duties. Hash-chain checking and local file permissions are useful inspectability measures, not externally anchored audit guarantees. The read-only HTML workbench is local and not an authenticated hosted service. File adapters and optional dispatch do not imply live scanner integrations. Before a customer rollout, agree approved data, identity, execution isolation, egress, credentials, retention, cancellation, recovery, observability and budget controls. Production publication authority needs a distinct design.

## 14. Lead a customer working session

Treat this as a collaborative customer working session. The repository is optional supporting evidence for a design discussion. Ask clarifying questions, state assumptions and explain tradeoffs. Discover the current workflow, stakeholders, approved data, constraints and desired business outcome. If new information changes a tool, identity, data or deployment assumption, revise the affected architecture and pilot instead of defending the original design. Use the whiteboard only when it helps. The billing example is an invented practice case and must not be assumed to match the provided customer scenario.

## 15. A pilot should lead to an operating decision

Agree the business problem and baseline before setting targets. Measure investigator and reviewer effort, accepted fixes, time to a supported decision, false fixes, proof gaps and operating cost. Include sample size and incomplete attempts. The local reference checks provide no model-quality score or measured ROI. A focused customer pilot should add one approved real source and one useful AI contribution, with labeled positive and negative cases, explicit execution boundaries, failure handling and an accountable reviewer. End with a concrete next owner, evidence requirement, date and stop/revise/expand decision.

## 16. Sources and evidence boundaries

Use current public product documentation as the product contract, and the repository source and tests as the implementation evidence. This deck contains no confidential recruiter correspondence, customer data, inferred internal roadmap or reconstructed interview question. OpenFix is an independent project. Synthetic source fixtures and trusted local checks exercise the workflow. They establish no live security-scan coverage, OpenAI model quality, merge or deployment result. Rebuild commands and detailed evidence live in the repository, outside these presentation slides.
