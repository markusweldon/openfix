# A discovery-led customer working session

This workbook is a rehearsal aid for the supplied exercise format. It contains original prompts and decision tools, not predicted interview questions or a reconstruction of the scenario. No deck or prepared implementation is required for the exercise.

## The objective

Help a customer make a defensible decision about a useful, secure AI-enabled workflow. Demonstrate how you discover the problem, choose capabilities, bound authority, define proof, plan execution, communicate value, and adapt when an assumption changes.

## A flexible five-part whiteboard

Draw five areas, or open the [editable Excalidraw template](customer-workflow.excalidraw), and fill them from the customer's answers:

1. **Outcome and people:** what hurts, who is affected, sponsor, operator, security owner, service owner, success.
2. **Current workflow and evidence:** inputs, tools, assets, versions, queues, handoffs, baseline delay and existing controls.
3. **Smallest useful AI step:** what the model contributes, what a native product already does, what integration is needed, what stays deterministic or human-owned.
4. **Boundaries and failure behavior:** data flow, identity, read/write authority, execution environment, review, audit, egress, cancellation and rollback.
5. **Pilot and decision:** examples, labels, proof, measures, owners, milestones, stop conditions and expansion criteria.

If the customer describes an AI application, add adversarial behavior evaluation. If the problem is source-code remediation, focus on finding validity and exact-patch verification. If the constraint is cloud exposure or runtime investigation, establish asset/version identity and operational ownership first.

## Map each assessment area to a concrete behavior

| Focus area | What to demonstrate |
| --- | --- |
| Discovery and framing | Ask about the bottleneck, business consequence, users, stakeholders, existing workflow and constraints before selecting tools |
| AppSec judgment | Explain attacker control, reachability, failed invariant, prerequisites and supported impact; distinguish uncertainty from a disproved claim |
| Practical AI architecture | Choose between native product use, a thin integration and custom orchestration; explain where the model adds value |
| Controls and readiness | Draw data and authority boundaries, name identities, separate consequential actions, and explain incomplete/failed outcomes |
| Evaluation and evidence | Define the accepted proof, legitimate behavior, negative cases and reviewer standards before execution |
| Business impact | Tie the pilot to investigator/reviewer effort and accepted outcomes, with a measured baseline and honest limitations |
| Communication | Give a concise recommendation for the sponsor and enough implementation detail for the practitioner |
| Adaptability | Restate a changed assumption, show the affected design decision, revise scope, and retain the remaining uncertainty |

## Questions that change the design

- Where exactly does work wait today, and which part would the customer actually pay to improve?
- What does the customer already have: Codex Security, scanners, asset inventory, issue tracking, observability and change controls?
- Which code, logs and data may leave the environment? Which retention and residency requirements apply?
- What can be joined reliably across repository revision, deployed service, cloud asset and runtime event?
- Who may authorize investigation, local code changes, PR publication, merge and deployment?
- What constitutes a true positive and an acceptable fix in this environment?
- What happens if the model is wrong, the environment cannot reproduce, an owner is unknown, or CI is pending?
- What is the smallest pilot that yields an operating decision rather than another impressive demo?

## A reusable recommendation shape

“Given the bottleneck and constraints, I recommend piloting **[one workflow]** for **[one scope]**. We will use **[native capability]** and add **[specific integration]**. The agent may **[bounded actions]**; **[named owner]** authorizes consequential changes. Success requires **[evidence and measures]**, compared with **[baseline]**. We need **[inputs and owners]** first. If **[stop condition]** occurs, we pause or revise. The next decision is **[expand, change, or stop]** after **[agreed milestone]**.”

Use your own language. This is a reasoning scaffold, not a memorized pitch.

## Practice three pivots

**Source cannot leave the customer's network.** Revisit the documented execution and data path. Do not assume a local executor means all model context stays local. Reduce the data scope or choose an approved architecture and record the remaining access gap.

**The patch fixes the reproducer but breaks legitimate behavior.** Keep verification failed, explain why the business requirement is unmet, and return to remediation. Agent completion does not change the verdict.

**The customer wants immediate production action.** Clarify incident urgency, blast radius, authorized operator, reversible containment and rollback. Adapt the pilot/change path; do not quietly convert a code-review workflow into autonomous production authority.

## What to prepare before the call

Understand the native finding/evidence/patch workflow and the product boundaries in the [product map](product-landscape.md). Practice one positive and one uncertain outcome. Be ready to draw the five-part whiteboard and explain a pilot. Use the deck as a reference library; the live conversation should follow the provided scenario and permitted tools.
