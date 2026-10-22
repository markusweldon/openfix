# OpenFix roadmap

The direction is an executable customer reference workflow: **customer context → security investigation → owned, verified changes**. The preparation materials and standalone lifecycle prototype are on `main`; the running CLI remains the v1 Cursor remediation application.

Start with the [prioritized repository plan](docs/prep/repo-strategy.md). It documents the current v1, the disconnected lifecycle prototype, the specific assurance gaps to address, and the next implementation increments with acceptance criteria.

For the customer exercise, use the [working-session workbook](docs/prep/exercise-workbook.md) and [product map](docs/prep/product-landscape.md). The [preparation pack](docs/prep/README.md) also includes an editable whiteboard, diagrams, and a visual reference deck.

| Stage | Status | Completion evidence |
| --- | --- | --- |
| v1 remediation adapter | Implemented | Report import, explainable routing, Cursor jobs and PR CI observation; see [walkthroughs](DEMO.md) for limits |
| Lifecycle domain | Standalone prototype | Software tests and a labeled simulation; no live scan or operational authentication |
| Persistent customer case workflow | Next increment | The actual CLI stores cases, evidence and decisions; restarts preserve them; corrupt state and invalid policy fail explicitly |
| One real security-to-change path | Proposed | A supported native or programmable security path, traceable source evidence, exact-patch verification and human review, including failed/incomplete outcomes |
| Context, workbench and evaluation | Proposed | One inspected asset/version/owner join, an interface over real state, representative negative cases and a measured pilot decision |

Native Codex Security integrations, isolated execution controls, durable evidence, authenticated review, operational context connectors and agent evaluation must be implemented and verified before being described as working capabilities. Retain the useful v1 adapters while bringing them under the lifecycle's case and evidence contracts.
