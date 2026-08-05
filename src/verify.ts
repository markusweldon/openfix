/**
 * Pre-merge verification checklist for remediation PRs.
 *
 * Interview talking point:
 *   Agent proposes a fix. CI + deterministic scanners re-check it.
 *   Humans authorize merge. The agent never "grades its own homework."
 */
export function printVerifyChecklist(prUrl?: string): void {
  console.log(`OpenFix pre-merge verification
================================
Remediation PRs are NOT merge-ready when the agent finishes.
They must clear the same gates as any other enterprise change.

${prUrl ? `PR under review: ${prUrl}\n` : ""}Required before merge
--------------------
[ ] 1. Agent-local checks (done in Cursor cloud VM)
      - Regression test added/updated when practical
      - Agent ran project tests (e.g. npm test) and reported results in PR

[ ] 2. PR CI (branch protection — system of record)
      - Open the fix PR → Checks: "App CI (verify fix PR)"
      - Unit tests PASS on the fix branch

[ ] 3. Deterministic scanner re-run on the FIX PR (not the agent claiming "fixed")
      - Same Semgrep / OSV / CodeQL / Snyk job as feature PRs
      - Original finding cleared or severity reduced in fresh SARIF
      - Do NOT trust agent prose alone — require scanner evidence

[ ] 4. Human authorization
      - AppSec / eng reviewed Diff + OpenFix provenance block
      - human_only findings (secrets/critical/auth) were NOT auto-merged by bots
      - No force-push; no direct push to main (hooks + branch protection)

[ ] 5. Merge only after 1–4
      - OpenFix never auto-merges

Branch protection checklist (target repo settings)
-------------------------------------------------
[ ] Require pull request before merging
[ ] Require status checks to pass (test + scanner workflows)
[ ] Require conversation resolution / review from CODEOWNERS as needed
[ ] Block force pushes to main
[ ] Restrict who can push to main

Where OpenFix itself runs in CI
-------------------------------
  Repo workflow: "OpenFix: SARIF → fix PRs" (manual Run workflow)
  = production placement of ingest → triage → Cursor remediate
  Demo live path on your laptop is the same code: openfix remediate
`);
}
