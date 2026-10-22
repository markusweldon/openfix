# OpenFix preparation pack

**Purpose:** rehearse a discovery-led customer working session and make an evidence-backed plan for this repository. Start from the provided scenario and constraints. This is an independent reference design and original practice material, not an OpenAI product or a reproduction of an interview exercise.

## Start here

- [Exercise workbook](exercise-workbook.md) — discovery, architecture, pilot decisions, and adapting to constraints.
- [Prioritized repository strategy](repo-strategy.md) — what to keep, refactor, retire, and implement next.
- [Product and operating-model map](product-landscape.md) — Defense Factory, Daybreak, Codex Security surfaces, and Promptfoo.
- [Editable Excalidraw whiteboard](customer-workflow.excalidraw) — a flexible five-part canvas.
- [Visual reference PDF](openfix-customer-workflow.pdf) — purple/synthwave gradients, with core canvases first and details as references.
- [Editable PowerPoint](openfix-customer-workflow.pptx) — includes speaker notes and editable gradients.
- [Talk track](talk-track.md) — concise prompts and source links for each slide.
- [Current v1 workflow](diagrams/current-v1.svg), [proposed full lifecycle](diagrams/lifecycle.svg), and [target architecture](diagrams/architecture.svg) — scalable diagrams with PNG and Mermaid counterparts.
- [Customer discovery and pilot worksheet](pilot-worksheet.md).
- [Architecture contracts and implementation status](refactor-plan.md).
- [Verification and limits](validation.md).

No presentation or advance implementation is required by the supplied exercise format. Use the deck as a visual library and rehearsal aid. The live discussion should follow the customer problem, assumptions, constraints, and permitted tools.

## What the assets claim

The existing OpenFix application is a Cursor-based scanner-to-remediation orchestrator. Its source code remains the record of implemented behavior. The proposed lifecycle expands discovery, evidence, validation, triage, remediation, verification, review, and closure. The diagrams explicitly label that target architecture.

The runnable lifecycle model under `src/lifecycle/` is a standalone prototype of decision gates, not a completed integration with every product in the diagrams. It is not wired into the running CLI. The new workflow's live Codex Security integration, isolated execution controls, trusted publication and production controls require implementation and verification. The v1 Cursor path already creates PRs; that does not supply the proposed artifact-bound review and publication service. Demo or simulated evidence must remain labeled.

No customer results, reduction percentages, cost savings, or production deployments are asserted in this pack.

## Rebuild the assets

From the repository root, with Python, `python-pptx` and Pillow installed:

```bash
python scripts/build-prep-assets.py
python scripts/build-whiteboard.py
```

The scripts generate the PowerPoint, SVG/PNG diagrams, talk track, and editable Excalidraw canvas. The whiteboard generator uses only the Python standard library. If LibreOffice is available, export the PDF with:

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
