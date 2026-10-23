# OpenFix preparation pack

**Purpose:** explain OpenFix's customer value and architecture by reading the repository. No application playback or live demonstration is required. Start from the customer's scenario and constraints. This is an independent project, not an OpenAI product or a reconstruction of an interview scenario.

## Start here

- [Repository walkthrough](../repository-walkthrough.md) — a value-led reading path through the code and tests.
- [AI security and DevSecOps](../ai-security-model.md) — what AI changes and why the harness exists.
- [Detailed architecture diagrams](../architecture.md) — GitHub-rendered Mermaid for components, trust boundaries, evidence, lifecycle, handoffs and production evolution.
- [Exercise workbook](exercise-workbook.md) — discovery, architecture, pilot decisions, and adapting to constraints.
- [Prioritized repository strategy](repo-strategy.md) — what to keep, refactor, retire, and implement next.
- [Product and operating-model map](product-landscape.md) — Defense Factory, Daybreak, Codex Security surfaces, and Promptfoo.
- [Three editable Excalidraw architecture whiteboards](../whiteboards/README.md) — customer value, system boundaries and proof before approval, with SVG/PNG previews.
- [Blank customer-discovery canvas](customer-workflow.excalidraw) — a flexible five-part workspace to fill from the customer's answers.
- [Visual reference PDF](openfix-customer-workflow.pdf) — optional purple/synthwave repository and value companion.
- [Editable PowerPoint](openfix-customer-workflow.pptx) — includes speaker notes and editable gradients.
- [Talk track](talk-track.md) — concise prompts and source links for each slide.
- [Optional legacy Cursor path](diagrams/current-v1.svg), [case lifecycle](diagrams/lifecycle.svg), and [local workflow architecture](diagrams/architecture.svg) — scalable diagrams with PNG and Mermaid counterparts.
- [Customer discovery and pilot worksheet](pilot-worksheet.md).
- [Architecture contracts and implementation status](refactor-plan.md).
- [Verification and limits](validation.md).

No presentation or advance implementation is required by the supplied exercise format. Use the deck as a visual library and rehearsal aid. The live discussion should follow the customer problem, assumptions, constraints, and permitted tools.

## What the assets claim

OpenFix 0.2 is the running case workflow: import/correlate observations, assess existing enrichment, add exact context, validate, prioritize, accept scope, record/verify a patch, review, and retain the decision. Original producer claims remain attributed. The original Cursor path is an optional executor.

The lifecycle domain operates on persistent cases through the default CLI. Read the synthetic fixture inputs and tests to inspect actual probe behavior, failed fixes and committed-diff verification. Native product scans, model execution and deployment were not performed for these checks. Authenticated identity/evidence, isolated customer-code workers and live operational connectors remain production work. Local actor assertions and operator rollout attestations are labeled accordingly.

No customer results, reduction percentages, cost savings, or production deployments are asserted in this pack.

## Rebuild the assets

From the repository root, with Python, `python-pptx` and Pillow installed:

```bash
python scripts/build-prep-assets.py
python scripts/build-whiteboard.py
python scripts/build-architecture-whiteboards.py
```

The scripts generate the PowerPoint, SVG/PNG diagrams, talk track, discovery canvas and three editable architecture whiteboards. The whiteboard generators use only the Python standard library; architecture previews are exported from Excalidraw. If LibreOffice is available, export the PDF with:

```bash
soffice --headless --convert-to pdf --outdir docs/prep docs/prep/openfix-customer-workflow.pptx
```

The PDF and PPTX are checked in so viewing them does not require these tools. Mermaid sources accompany the diagrams.

## Public references

- [Codex Security overview](https://help.openai.com/en/articles/20001107)
- [Run and review a scan](https://learn.chatgpt.com/docs/security/plugin/scans)
- [Fix and verify findings](https://learn.chatgpt.com/docs/security/plugin/fix-findings)
- [Codex Security CLI reference](https://learn.chatgpt.com/docs/security/cli/reference)
- [Codex Security TypeScript SDK](https://learn.chatgpt.com/docs/security/sdk)
- [Codex authentication](https://developers.openai.com/codex/auth)
- [Cloud-specific usage and billing](https://learn.chatgpt.com/docs/security/faq)
- [Defense Factory](https://openai.com/the-defense-factory/)
- [Daybreak](https://openai.com/daybreak/)
- [Promptfoo agent evaluation](https://www.promptfoo.dev/docs/red-team/agents/)

Product contracts can change. Check access, supported authentication, execution permissions, output schemas, and data handling in the current documentation before implementation.
