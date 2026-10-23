# OpenFix 0.2: a findings-to-decision walkthrough

Run this from the repository root with Node.js 22.13+:

```bash
node src/openfix.mjs demo --out /tmp/openfix-workbench.html
```

Open the HTML file. The command prints the case store and temporary reference repositories. Keep that directory for follow-up commands; the demo refuses to overwrite an existing `--dir`. Use `node src/openfix.mjs help` for options.

## 1. Preserve and correlate the inputs

The integrated demo imports five synthetic reports through the same adapters used by the CLI:

- SARIF and GitHub code-scanning observations of the same scoped tenant issue.
- A dependency finding with existing reachability enrichment.
- A cloud/context report whose owner conflicts with the asset inventory.
- A suspected tenant issue in an already protected service.

They form four cases. Each observation keeps its producer, source identifier, original redacted content and input-artifact digest. Matching observations are grouped by subject/revision/location/taxonomy; the application does not discard one producer's evidence or treat the grouping as proof.

## 2. Inspect enrichment before adding more

The context manifest supplies owner, exposure, business criticality and deployed revision. The join requires the exact asset, repository and source revision. Source excerpts come from a clean repository at that revision. Repeating the same enrichment reuses five existing evidence records in the primary case.

The evidence plan explains whether to collect, refresh, reuse, review producer validation or resolve a conflict. Inspect the ledger's source, authority, timestamps and revision. Unknown and stale evidence stays visible. An imported "confirmed" verdict cannot make a case independently confirmed.

## 3. Investigate useful negative outcomes

The installed tenant profile executes against the actual reference code:

- The vulnerable lookup returns another tenant's invoice: **confirmed**.
- The protected lookup denies that request and retains legitimate access: **disproved**, then dismissed with a reason.
- The dependency case has no installed runtime profile: **inconclusive**. Its failed attempt stays in the denominator and record.
- Conflicting owner claims remain unresolved; importing inventory does not overwrite the original producer.

The profile is a narrow reference application check, not a general vulnerability scanner. It runs locally after explicit execution and does not establish a production isolation boundary.

## 4. Reject a false fix

A reviewer accepts the confirmed case with an owner, rationale and priority. The demo records a real committed diff that denies all invoice requests. It blocks the exploit but breaks the owning tenant's access, so verification fails and approval is rejected.

The corrected diff adds the tenant predicate. Recording it invalidates prior patch decisions. The independent local verifier checks its exact Git head and diff digest, observes both checks passing, and a different reviewer approves that artifact. No merge or deployment happens. The resulting state is `approved_for_change`, not closed.

## 5. Continue with the real CLI

Use the paths and case ID printed by the demo:

```bash
node src/openfix.mjs list --store /tmp/DEMO-DIRECTORY/workflow
node src/openfix.mjs show CASE_ID --store /tmp/DEMO-DIRECTORY/workflow
node src/openfix.mjs plan CASE_ID --store /tmp/DEMO-DIRECTORY/workflow \
  --out /tmp/new-openfix-task
node src/openfix.mjs serve --store /tmp/DEMO-DIRECTORY/workflow --port 4317
```

The workbench is read-only and binds to loopback. It shows actual persisted cases, evidence, attempts, artifacts and decisions. The downloadable [recorded casebook](docs/demo/workbench.html) uses the same renderer. It contains only the reference demo's data.

## Bring a customer case

Use [input contracts](docs/input-contracts.md) to import real source artifacts, customer brief and context. Choose a documented native Codex Security workflow or an approved executor after discovering the customer's constraints. Exported task packets preserve those boundaries and evidence gaps.

The optional Cursor bridge needs installed dependencies and Cursor authentication. The original pipeline is available through `npm run legacy -- ingest ...`, `triage`, `remediate`, `status`, `resume`, and `verify`. Legacy CI observation returns 2 for incomplete/unavailable results and does not independently prove a fix.

## Discuss the customer decision

Agree the bottleneck, baseline, owner, allowed data/actions and accepted proof before broadening the pilot. Measure investigator/reviewer effort, accepted outcomes, false fixes, latency and total attempted-run cost. The example has no measured customer baseline or ROI result. Adapt the workflow if the customer changes data residency, execution, identity or rollout constraints.
