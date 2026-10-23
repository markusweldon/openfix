# Architecture diagram sources

The [architecture guide](../architecture.md) renders these Mermaid sources alongside their rationale, tradeoffs and implementation links. Read the diagrams there on GitHub; no running application is required.

| Source | Question it helps explain |
| --- | --- |
| [System components](system-components.mmd) | What runs locally, what is external, and where do data and actions cross a boundary? |
| [Evidence decisions](evidence-decisions.mmd) | What can we reuse, what needs investigation, and what authority does the evidence carry? |
| [Case lifecycle](case-lifecycle.mmd) | What allows work to advance, and what happens when proof fails or context changes? |
| [Agent handoff sequence](agent-handoff-sequence.mmd) | How does an investigator become an authorized remediation task, and how is its output reviewed? |
| [Case data model](case-data-model.mmd) | How do cases retain producer observations, evidence, unsuccessful attempts and artifact identity? |
| [Proposed production evolution](production-evolution.mmd) | Which identity, isolation, orchestration and deployment-evidence components still need implementation? |

The [AI security guide](../ai-security-model.md) adds diagrams separating security with AI from security of AI, and fix verification from agent-behavior evaluation. The [README](../../README.md) contains a smaller system overview. Together these are nine diagrams; the production architecture and agent-evaluation lane are explicitly proposed work.
