# OpenFix talk track

OpenFix 0.2 is an implemented local case workflow. This original rehearsal aid uses synthetic source reports and real local fixture checks. Start with discovery and use only the visuals that help.

## 01. Evidence to action.

OpenFix is now an implemented local workflow, not a standalone lifecycle prototype. The default CLI persists cases, imports evidence, assesses context, validates supported cases, records acceptance, binds a committed diff, verifies it and records human review. The recorded demo uses synthetic reports and actual local fixture probes. It makes no model call, live scanner call, merge or deployment. Use these visuals only if they help the customer conversation; the exercise requires no prepared presentation.

## 02. Preserve knowledge. Investigate the gaps.

Start by asking where customer effort is lost: finding investigation, ownership, acceptance, remediation or review. Security tools may already provide reachability, validation, exploitability, ownership, runtime and code evidence. OpenFix preserves that material and plans around missing or conflicting evidence rather than blindly rerunning every stage. A priority suggestion does not grant execution authority. Producer assertions are not automatically independent proof.

## 03. Many observations, one persistent case

Adapters import local SARIF, GitHub code-scanning exports, Snyk JSON and supported Codex Security scan JSON, along with a generic finding envelope. These are file adapters, not live service connectors. Original observations remain linked to artifact digests and source identity. Correlation is deterministic and conservative; it is not a universal semantic deduplication engine. The local store uses atomic replacement, a writer lock and a hash-chained event audit with a state checkpoint. These mechanisms do not provide authenticated multi-tenant storage or an external tamper-proof ledger.

## 04. Reuse evidence and preserve its authority

Evidence records preserve upstream assertions separately from local evidence and explicit reviewed adoption of external validation. Context joins require the exact repository, asset and revision. Subject-mismatched evidence cannot silently change current context. The default freshness window is seven days, with explicit expiry supported; missing dates remain unknown and future timestamps are flagged. The freshest record per origin, producer and kind contributes to current assessment. Fresh contradictions remain visible instead of being overwritten by source precedence. The plan can reuse with provenance, refresh or verify, collect, resolve a conflict, or review upstream validation. A new or expired context record invalidates accepted scope where required.

## 05. The implemented local architecture

This diagram describes the implemented local architecture. The default src/openfix.mjs CLI calls the workflow modules and persistent store. File adapters supply findings and context, and a customer brief records goals and boundaries. The same stored cases feed assessment, the read-only HTML workbench and agent task packets. The built-in tenant-isolation profile runs trusted local fixture code only after explicit execution authorization. Its supported subject is CWE-639 at src/invoices.mjs:3; mismatched findings remain inconclusive. Optional Cursor dispatch calls the retained executor bridge. Neither local child-process bounds nor named actor labels are a production isolation or identity boundary. No live Codex Security scan is invoked by the demo.

## 06. Each case carries evidence and decisions

The path is implemented through the default CLI. Imported evidence is assessed before additional investigation. Validation can confirm, disprove or remain inconclusive. Acceptance records owner, priority, rationale and context. A committed diff is then recorded with exact base, head and digest. A different actor runs the approved verification profile and a reviewer approves the exact patch hash. New context or a replacement patch can invalidate earlier decisions. Review does not merge or deploy. Rollout and closure commands require separate change records, exact deployed revision and post-change evidence; the demo stops at approved_for_change.

## 07. A workbench over the actual case store

This is the actual generated workbench, not a design mockup. It reads the durable workflow store, presents case assessment, source observations, customer context, validation and change gates, an evidence plan, a provenance ledger and audit history. The slide crops the screenshot to the main workspace; open the HTML or full screenshot for detailed inspection. The interface is read-only. Suggested urgency is separate from the priority accepted by a reviewer. The recorded-demo banner states that reports are synthetic and local validation checks are real; there is no live scanner, model call or deployment.

## 08. The demo deliberately keeps four outcomes

The synthetic reports produce five observations and four correlated cases. The tenant-isolation profile executes four times: vulnerable baseline, protected baseline, deliberately broken patch and corrected patch. The dependency profile is unavailable, creating a fifth attempted check with an incomplete outcome, not a successful reproduction. The protected case is disproved and dismissed. The cloud owner contradiction remains unresolved. Report the denominator honestly: these reference checks demonstrate workflow mechanics and negative cases, not model performance, generalized vulnerability coverage or a customer ROI result.

## 09. A patch can block the attack and still fail

The reference fixture initially returns another tenant invoice. The first committed patch denies every request. It blocks the attacker but also breaks the legitimate owning tenant, so regression verification fails and the workflow rejects an approval attempt. The corrected committed patch adds the tenant predicate and preserves the legitimate lookup. Both checks pass and the reviewer approves that exact hash. The patch engine is a deterministic reference code edit in this demo; do not describe it as a model-generated fix. This is evidence of an important evaluation property: security-only success cannot justify a broken product.

## 10. Approval belongs to an exact change

Patch recording binds a real git diff from the recorded base to a committed head, hashes the binary diff and rejects more than twenty changed files. Verification checks the repository snapshot, exact head and digest before executing the selected profile. The reference verifier permits only invoice-file changes; changes beyond that surface remain incomplete. Missing prerequisites or an artifact mismatch produce an incomplete result rather than success. A local verifier label must differ from the author label. Review requires passing independent verification and the exact patch hash. Labels are audit assertions supplied by the operator, not authenticated identities or a separation-of-duties enforcement boundary. Merge, deployment and post-change closure remain separate decisions.

## 11. Give agents a bounded security case

The agent packet carries the case subject, customer brief, observations, current evidence, gaps, action boundary and expected output contract. Instructions distinguish producer assertions, source analysis and runtime proof, and treat code comments, finding text and tool results as data rather than instructions. Packets are handoff artifacts; they do not themselves invoke an OpenAI model. The repository includes .agents skills for case investigation and patch verification. Optional Cursor dispatch reuses the existing executor, requires accepted scope, --execute, --publish-draft and a named --actor, and is not exercised in the recorded demo. Returned PRs still need exact-patch import, verification and review.

## 12. Use native security capabilities

This alignment uses public descriptions, not a claim about internal OpenAI architecture or an official integration. Start with native Codex Security functionality and use the documented contract of the customer environment. OpenFix imports supported Codex scan JSON but does not run a live scan in the demo. Defense Factory describes a continuous operating approach, and Daybreak encompasses a wider stack. Promptfoo helps evaluate AI applications and adversarial agent behavior; it is relevant when a model-driven step exists. Do not claim Promptfoo execution in this demo. ChatGPT Pro familiarization does not establish that every Cloud scan is included; confirm product access and billing separately.

## 13. What remains for production

The trusted local reference profile is a bounded child process, not a container, VM or network sandbox for arbitrary customer code. Actor labels do not establish authentication, RBAC or enterprise separation of duties. Hash-chain checking and local file permissions are useful inspectability measures, not externally anchored audit guarantees. The read-only HTML workbench is local and not an authenticated hosted service. File adapters and optional dispatch do not imply live scanner integrations. Before a customer rollout, agree approved data, identity, execution isolation, egress, credentials, retention, cancellation, recovery, observability and budget controls. Production publication authority needs a distinct design.

## 14. Lead a customer working session

Treat this as a collaborative customer exercise, not a product pitch or a requirement to demo OpenFix. Ask clarifying questions, state assumptions and explain tradeoffs. Discover the current workflow, stakeholders, approved data, constraints and desired business outcome. If new information changes a tool, identity, data or deployment assumption, revise the affected architecture and pilot instead of defending the original design. Use the whiteboard only when it helps. The billing example is an invented practice case and must not be assumed to match the provided customer scenario.

## 15. A pilot should lead to an operating decision

Agree the business problem and baseline before setting targets. Measure investigator and reviewer effort, accepted fixes, time to a supported decision, false fixes, proof gaps and operating cost. Include sample size and incomplete attempts. The local demo gives no model-quality score and no measured ROI. A focused customer pilot should add one approved real source and one useful AI contribution, with labeled positive and negative cases, explicit execution boundaries, failure handling and an accountable reviewer. End with a concrete next owner, evidence requirement, date and stop/revise/expand decision.

## 16. Sources and evidence boundaries

Use current public product documentation as the product contract, and the repository source and recorded demo as the implementation evidence. This deck contains no confidential recruiter correspondence, customer data, inferred internal roadmap or reconstructed interview question. OpenFix is an independent project. The demo imports synthetic source reports and executes real local fixture checks; it invokes no live security scan, OpenAI model, merge or deployment. The workbench screenshot is an actual generated local report. Rebuild commands and detailed evidence live in the repository, outside these presentation slides.
