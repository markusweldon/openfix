/**
 * Prompts sent to the Cursor agent.
 *
 * Interview talking point:
 *   The prompt encodes separation of duties in writing:
 *   scanner detected → agent remediates → human merges.
 *   PR body must cite tool/ruleId/fingerprint (audit trail).
 *   Agent must NOT claim "fixed" until CI re-runs the deterministic scanner.
 */
import type { Finding } from "../types/finding.js";

/** Initial remediation turn for Agent.send(...). */
export function buildRemediationPrompt(finding: Finding): string {
  const location = finding.file
    ? `${finding.file}${finding.startLine ? `:${finding.startLine}` : ""}`
    : "(no file location provided)";

  return `You are OpenFix, an enterprise remediation agent.

## Separation of duties (mandatory)
- Detection came from an EXTERNAL deterministic security scanner — not from you.
- You propose a fix only. Do NOT merge. Do NOT push to main/master.
- Open (or update) a pull request for HUMAN review.
- Cite the scanner provenance below in the PR body.

## Scanner provenance
- Tool: ${finding.tool}
- Rule ID: ${finding.ruleId}
- Severity: ${finding.severity}
- Category: ${finding.category}
- Fingerprint: ${finding.fingerprint}
- Finding ID: ${finding.id}
- Title: ${finding.title}
- Message: ${finding.message}
- Location: ${location}

## Required PR body sections
1. **Detection** — tool, ruleId, severity, fingerprint (scanner is source of truth)
2. **Remediation** — what you changed and why
3. **Verification** — tests you ran locally in this environment + how CI should validate
4. **Scanner re-run gate (mandatory language)** — include this exact intent:
   "CI must re-run the deterministic scanner on this PR. Do not treat this issue as
   closed until fresh SARIF/results show the finding cleared or reduced. The agent
   does not self-attest that the vulnerability is fixed."
5. **Authorization** — "Merge requires human review. OpenFix does not auto-merge."

## Constraints
- Minimal change set; do not refactor unrelated code.
- Prefer dependency bumps / targeted code fixes matching the finding.
- Add or update a regression test when practical; run the project test command and report results.
- Never commit secrets. Never force-push. Never delete .git or cloud credentials.
- If the fix is unsafe or unclear, stop and explain in the PR / response instead of guessing.
- Do NOT claim the vulnerability is fully remediated until CI scanner evidence exists.
`;
}

/** Follow-up turn for Agent.resume → send (review feedback, extra tests, etc.). */
export function buildResumePrompt(extra: string): string {
  return `Continue the OpenFix remediation.

Human follow-up instruction:
${extra}

Remember:
- Detection was from an external scanner; you only remediate.
- Open/update a PR for human review; never merge to main.
- CI must re-run the deterministic scanner; do not self-attest that the finding is fixed.
`;
}
