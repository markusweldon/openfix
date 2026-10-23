# OpenFix

**Findings to evidence. Evidence to action.** OpenFix 0.2 is a local findings-intelligence and controlled-remediation workbench. It takes reports from different tools, preserves their existing enrichment, investigates evidence gaps, and carries decisions through validation, triage, exact-patch verification and review.

![OpenFix review workbench](docs/demo/workbench.png)

## Run the integrated workflow

The core uses Node.js 22.13+ and its standard library. From the repository root:

```bash
node src/openfix.mjs demo --out /tmp/openfix-workbench.html
```

Open the resulting HTML file. The command prints the persistent store location; inspect or serve the same cases with:

```bash
node src/openfix.mjs list --store /tmp/PRINTED-DEMO-DIRECTORY/workflow
node src/openfix.mjs serve --store /tmp/PRINTED-DEMO-DIRECTORY/workflow
```

The [recorded interactive demo](docs/demo/workbench.html) is checked in for download and local viewing. The [walkthrough](DEMO.md) explains its decisions and commands. The reports are synthetic; the reference application, vulnerability probe, bad patch and corrected patch are real local code executions. No live scan, model request or deployment is claimed.

## What happens to a finding

| Stage | Implemented behavior |
| --- | --- |
| **Import and correlate** | SARIF, GitHub code-scanning alerts, Snyk JSON, Codex Security scan JSON and OpenFix envelopes become scoped cases. Original observations and supplied enrichment remain attributed to their producer. Grouping is an investigation aid, not proof of equivalence. |
| **Assess existing evidence** | Keep producer claims separate from local observations and operator attestations. Check subject revision, age and conflicting values; never promote an imported verdict to independent confirmation. |
| **Enrich the gaps** | Join asset/owner/exposure/deployed-version context by exact identity, inspect source at a clean pinned revision, and inspect dependency versions when lockfile evidence exists. Reuse matching current evidence and make missing or stale signals visible. |
| **Validate and prioritize** | Record confirmed, disproved or inconclusive outcomes. The executable reference profile tests tenant isolation and legitimate access. Other environments can supply explicitly reviewed evidence. Priority explains severity, exposure, business importance and evidence inputs; it does not grant authority. |
| **Plan and remediate** | Accept an owner, rationale and bounded scope. Export a native-agent task packet or explicitly dispatch an eligible case through the optional Cursor adapter. Secrets and infrastructure changes route to their responsible specialist. |
| **Verify and review** | Bind a real Git diff to its base/head and digest. Check the original issue and legitimate behavior at the exact changed head. Missing or failed checks block approval. Patch changes invalidate prior verification and review. |
| **Retain the decision** | Persist cases, evidence, unsuccessful attempts and an audit chain. Rollout and closure record explicit operator attestations; the application does not merge or deploy changes. |

The actual `openfix` / `dev` entry points now run this workflow. The lifecycle domain is integrated with persistent cases; it is no longer only a separate demonstration. The original Cursor pipeline remains available through `npm run legacy -- ...` and as an optional executor bridge.

## Bring reports and context

```bash
node src/openfix.mjs import findings.sarif github-alerts.json \
  --repository https://github.com/ORG/APP --revision REAL_COMMIT_SHA \
  --asset-id service:billing --brief customer-brief.json
node src/openfix.mjs enrich all --context asset-context.json
node src/openfix.mjs show CASE_ID
node src/openfix.mjs plan CASE_ID --out /tmp/new-investigation-packet
```

Use the actual repository and revision represented by the report. Unknown revisions stay unresolved. An older-revision enrichment is retained and excluded from current context. A completed or empty later scan never auto-closes an earlier case.

Read [input and evidence contracts](docs/input-contracts.md) for formats and examples, [architecture](docs/architecture.md) for boundaries, and `node src/openfix.mjs help` for the full command surface.

## OpenAI and existing tools

OpenFix follows the public [Defense Factory](https://openai.com/the-defense-factory/) pattern of inventory, discovery/import, validation, ownership and verified remediation. It integrates evidence and decisions around security capabilities rather than claiming to reproduce OpenAI's internal service.

- **Codex Security:** import a SARIF export or the documented `scan --json` wrapper, preserving findings, producer validation and coverage metadata. Repository/revision scope must be explicit when not available in the imported format. No Cloud API or authenticated live Cloud connector is invented.
- **Native Codex workflow:** export a bounded case packet and use the repository's [investigation](.agents/skills/openfix-investigate/SKILL.md) or [remediation](.agents/skills/openfix-remediate/SKILL.md) skill in the customer's approved host. No direct OpenAI API client or new API key is needed by the local orchestration core. Native product access and billing remain separate.
- **Cursor:** `dispatch CASE --engine cursor --execute --publish-draft --actor NAME` can use the existing SDK after case gates pass. This explicitly authorizes creating a draft pull request. Install dependencies and configure the existing Cursor credential first. This adapter was typechecked; no live Cursor job was executed for this release.
- **Promptfoo:** an optional future lane for evaluating agent behavior, including hostile evidence and unauthorized tool use. It is separate from verifying a code fix.
- **Endor Labs Agent Kit:** a [public reference](https://github.com/endorlabs/endor-labs-agent-kit) for task workflows and evidence/output contracts. No Endor API integration is claimed.

## Verify and develop

```bash
npm install --ignore-scripts
npm test
npm run typecheck
npm run build
npm run demo -- --out /tmp/openfix-workbench.html
```

The demo retains five source observations across four cases and five attempted validation/verification runs. It includes a reproduced vulnerability, a disproved report, an unavailable validator and conflicting ownership; a deny-all patch fails before the correct patch passes. These demonstrate software behavior, not detection accuracy or customer ROI.

## Scope and next work

The reference validator is a bounded local process with explicit execution. It is **not** a container or network sandbox; untrusted customer code needs an approved isolated worker. Local actor names and role checks are audit assertions, not enterprise identity or RBAC. Exported native-product evidence is preserved but its authenticity is not independently established by importing JSON. Recognized credential patterns are redacted; source/report handling still requires a suitable data policy.

Production identity, isolated workers, authenticated evidence ingestion, live connector qualification and deployment verification are the next increments in the [roadmap](ROADMAP.md). The [verification record](docs/prep/validation.md) distinguishes tested behavior from those remaining requirements.

The [purple visual reference deck and preparation pack](docs/prep/README.md) now describe this implementation. The supplied customer exercise requires no presentation; use the workbook and visuals as discussion aids.

## License

MIT
