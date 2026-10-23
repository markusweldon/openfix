# Product and operating-model map

Research checked on October 22, 2026. Product capabilities, access and billing can change. This page distinguishes documented capabilities from this repository's design proposals.

Endor Labs Agent Kit reference added after reviewing its public repository and output contract on October 23, 2026.

OpenFix 0.2 imports Codex Security's documented `scan --json` wrapper and SARIF, preserving native finding evidence and coverage metadata. It exports native-agent task packets and includes repository skills. This is file/contract integration; no authenticated live Cloud connector, live native scan or direct OpenAI API client is claimed. See [input contracts](../input-contracts.md) and [architecture](../architecture.md).

| Name | Documented role | Boundary for this project |
| --- | --- | --- |
| **Defense Factory** | OpenAI's continuous defensive operating model and reference architecture. It joins existing tools, system context, isolated execution, orchestration, policy, ownership and verification. | Learn the process and boundaries. OpenFix can demonstrate an integration workflow; it should not claim to be OpenAI's internal system. [Official description](https://openai.com/the-defense-factory/) |
| **Daybreak** | A broader governed cyber-defense stack spanning models, harness, security capabilities, access and ecosystem. | An umbrella for capabilities and deployment patterns, not a single scanner API to recreate. [Daybreak](https://openai.com/daybreak/) |
| **Codex Security Cloud** | Connected GitHub repository review and commit monitoring with finding/evidence and available fix workflows. | Use native capabilities when sufficient. Do not infer a general cloud-infrastructure or production-runtime scanner from its name. [Cloud setup](https://learn.chatgpt.com/docs/security/setup) |
| **Local Security plugin** | Code security workflows in a Codex conversation and local workbench. | Practical hands-on familiarization; distinguish it from the Cloud surface. [Plugin guide](https://learn.chatgpt.com/docs/security/plugin) |
| **Security CLI / SDK** | Documented programmable scans and structured findings, coverage and artifacts, with runtime and access prerequisites. | A candidate integration path for a custom customer workflow. Preserve the actual contract and failure states. [CLI](https://learn.chatgpt.com/docs/security/cli/reference), [SDK](https://learn.chatgpt.com/docs/security/sdk) |
| **Promptfoo** | Evaluation and adversarial security testing for AI applications and agents, including tool-use behavior. | Useful for evaluating OpenFix's agent or an AI customer application. Keep AI-behavior evaluation separate from proving a source-code vulnerability was fixed. [Red teaming](https://www.promptfoo.dev/docs/red-team/), [Agent testing](https://www.promptfoo.dev/docs/red-team/agents/) |
| **Endor Labs Agent Kit** | Reusable security-task workflows for coding assistants and portable runtimes, including findings investigation, remediation planning, dependency review and approval-gated remediation. Its portable contracts specify inputs, evidence, outputs, data gaps and runtime adapter responsibilities. | A design reference for customer tasks and evidence contracts. Endor-backed workflows require their documented platform access and adapters; none is integrated into OpenFix. [Repository](https://github.com/endorlabs/endor-labs-agent-kit), [AI SAST output contract](https://github.com/endorlabs/endor-labs-agent-kit/blob/main/portable/ai-sast-remediation/output-contract.md) |

## Pro and Cloud billing

ChatGPT sign-in supports subscription-backed local Codex use. That does not establish that every Codex Security surface is covered by included usage.

The current Cloud FAQ says repository and continuous scans set up after **October 1, 2026, 12:53 p.m. Pacific** are token billed and excluded from the plan's included usage allowance. The earlier covered continuous-scanning period ended October 21. Eligible accounts may have separate scanning credits. Confirm actual account access, credits and paid-usage settings before a Cloud run; this repository has not verified those account-specific details. [Cloud billing FAQ](https://learn.chatgpt.com/docs/security/faq), [Codex authentication](https://developers.openai.com/codex/auth).

## Promptfoo acquisition wording

OpenAI and Promptfoo announced an acquisition agreement on March 9, 2026, with intended integration of evaluation and security capabilities into Frontier. Both announcements describe closing conditions. The primary sources reviewed here do not establish completion of that integration or every current commercial entitlement. Use the public announcements accurately rather than inferring product behavior or an interviewer's biography. [OpenAI announcement](https://openai.com/index/openai-to-acquire-promptfoo/), [Promptfoo announcement](https://www.promptfoo.dev/blog/promptfoo-joining-openai/).

## Two different evaluation questions

**Does the security finding apply, and did the patch address it?** Use the source/attack path, prerequisites, reproducer where feasible, legitimate behavior and relevant regression evidence at the exact revision. Source-based support can be useful even when runtime proof remains incomplete. A failed reproduction can reflect an unsuitable environment. [Cloud evidence guidance](https://learn.chatgpt.com/docs/security/faq), [fix verification](https://learn.chatgpt.com/docs/security/plugin/fix-findings).

**Does the AI system behave safely and reliably?** Evaluate whether hostile reports, code comments or tool outputs can cause scope expansion, data leakage, unauthorized tool calls or approval bypass. Inspect actual tool traces and outcomes; a reassuring final answer is insufficient evidence of the actions taken. Promptfoo can support this lane when applicable. [Agent evaluation](https://www.promptfoo.dev/docs/red-team/agents/).

These questions can share a case/evidence store, but one passing result does not answer the other.
