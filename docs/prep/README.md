# OpenFix preparation pack

**Purpose:** rehearse a customer conversation about moving from security signals to reviewed, verified changes. This is an independent architecture proposal and original practice scenario, not an OpenAI product or a reproduction of an interview exercise.

## Start here

- [Presentation PDF](openfix-customer-workflow.pdf) — easiest format to read or share.
- [Editable PowerPoint](openfix-customer-workflow.pptx) — includes speaker notes.
- [Talk track](talk-track.md) — concise prompts and source links for each slide.
- [Current v1 workflow](diagrams/current-v1.svg), [proposed full lifecycle](diagrams/lifecycle.svg), and [target architecture](diagrams/architecture.svg) — scalable diagrams with PNG and Mermaid counterparts.
- [Customer discovery and pilot worksheet](pilot-worksheet.md).
- [Refactor scope and implementation status](refactor-plan.md).
- [Verification and limits](validation.md).

The deck is a preparation aid. A customer working session starts with discovery; use only the parts that fit the customer's problem. It is not necessary to deliver the whole presentation.

## What the assets claim

The existing OpenFix application is a Cursor-based scanner-to-remediation orchestrator. Its source code remains the record of implemented behavior. The proposed lifecycle expands discovery, evidence, validation, triage, remediation, verification, review, and closure. The diagrams explicitly label that target architecture.

The runnable lifecycle model under `src/lifecycle/` is a prototype of decision gates, not a completed integration with every product in the diagrams. Live Codex Security access, isolated execution, publication, and production controls require separate integration and verification. Demo or simulated evidence must remain labeled.

No customer results, reduction percentages, cost savings, or production deployments are asserted in this pack.

## Rebuild the assets

With Python and `python-pptx` installed:

```bash
python scripts/build-prep-assets.py
```

The script generates the PowerPoint, SVG/PNG diagrams, and talk track. If LibreOffice is available, export the PDF with:

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
- [ChatGPT and API billing](https://help.openai.com/en/articles/9039756-managing-billing-for-chatgpt-and-the-api-platform)

Product contracts can change. Check access, supported authentication, execution permissions, output schemas, and data handling in the current documentation before implementation.
