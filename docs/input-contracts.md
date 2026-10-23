# Input and evidence contracts

## Supported files

| Input | Detection and preserved fields |
| --- | --- |
| SARIF 2.x | `runs[]`, tool/rule, location, severity, version-control provenance, raw result and supplied enrichment |
| GitHub code-scanning export | Alert array or `{alerts:[]}`, rule, tool, most recent instance/revision/location and original alert |
| Snyk JSON | `vulnerabilities[]`, package/version, advisory, severity, original vulnerability and supplied enrichment |
| Codex Security `scan --json` | Documented `manifest`, `findings.findings`, `coverage`, turn and cost metadata; severity level, locations, original code/validation/attack-path evidence |
| OpenFix v2 | The source-neutral envelope below, with attributed existing enrichment and evidence |
| Legacy OpenFix v1 | Existing `{version:1, findings:[]}` exports, retaining original raw input |

Use `--repository`, `--revision` and `--asset-id` when the source format does not provide the required scope. These bind operator-supplied context; they are not independent proof that the original report matches the repository. Unknown revision cases remain unresolved. Unsupported envelope versions fail explicitly.

Codex Security support follows its [CLI JSON contract](https://learn.chatgpt.com/docs/security/cli/reference) and [SDK fields](https://learn.chatgpt.com/docs/security/sdk). A SARIF export is also supported. The importer does not call a Cloud API, validate an export's authenticity, execute a scan, infer complete coverage or promote native producer validation to independent proof. It preserves completion and coverage metadata separately.

## Source-neutral finding envelope

The following is a shape example; replace the revision with the actual immutable commit and use real timestamps before running it:

```json
{
  "schemaVersion": 2,
  "producer": "existing-security-tool",
  "repository": "https://github.com/ORG/APP",
  "revision": "REAL_IMMUTABLE_COMMIT",
  "assetId": "service:billing",
  "findings": [{
    "id": "producer-123",
    "ruleId": "tenant-check",
    "cwe": "CWE-639",
    "title": "Possible cross-tenant invoice lookup",
    "severity": "high",
    "category": "sast",
    "file": "src/invoices.mjs",
    "line": 3,
    "evidence": [{
      "kind": "reachability",
      "value": true,
      "revision": "EVIDENCE_SUBJECT_COMMIT",
      "collectedAt": "ACTUAL_ISO_TIMESTAMP",
      "sourceRef": "producer-investigation-reference"
    }]
  }]
}
```

Upstream evidence keeps its own revision, source reference, timestamp and expiration. A claim at another revision is retained and excluded from current context. Undated or expired claims require refresh/review. Default evidence age is seven days unless an explicit expiration is supplied; choose a customer policy before production.

Existing `enrichment` objects and common `validation`, `reachability`, `codeEvidence`, `rootCause`, `attackPath`, `runtimeEvidence`, `remediationTests` and related fields are retained. Original observations preserve additional producer fields even when no automatic enrichment extractor exists.

## Asset context and customer brief

```json
{
  "schemaVersion": 1,
  "assets": [{
    "assetId": "service:billing",
    "repository": "https://github.com/ORG/APP",
    "revision": "REAL_IMMUTABLE_COMMIT",
    "owner": "billing-team",
    "exposure": "internet",
    "criticality": "critical",
    "deployedRevision": "ACTUAL_DEPLOYED_COMMIT",
    "observedAt": "ACTUAL_ISO_TIMESTAMP",
    "evidenceRef": "inventory-record-reference"
  }]
}
```

Exposure accepts internet, internal or isolated. Unknown/malformed owner or exposure does not establish readiness. A deployed revision different from the finding revision remains an applicability gap. The context manifest is an attributed input, not an authenticated live connector.

`--brief` accepts a JSON customer brief. Record problem, stakeholders, goals, scope, data/action constraints, baseline and pilot decision. Brief text describes context; it cannot grant tool authority or override the executable workflow gates.

## Reviewed external validation

`validate CASE --evidence result.json --attest --actor REVIEWER` requires the exact finding revision, `method` (source or runtime), `verdict` (confirmed/disproved/inconclusive), `summary` and `limitations[]`. The result is stored as an operator attestation, not represented as execution performed by OpenFix. Imported report fields alone cannot invoke this operation. The production host must authenticate the reviewer and verify evidence origin.

The built-in `tenant-isolation` profile executes only the reference CWE-639 invoice lookup at `src/invoices.mjs:3` after `--execute`. Other cases remain inconclusive rather than inheriting its verdict. Reference patch verification also rejects changes outside that file. Missing profile, dirty/mismatched source, runtime error or incomplete probe remains inconclusive. Patch verification requires the exact changed head and diff digest, with security and legitimate-access checks passing. Other vulnerabilities require their own approved validation capability or reviewed external evidence.

The optional Cursor executor can create a draft pull request. `dispatch CASE --engine cursor --execute --publish-draft --actor OPERATOR` separately authorizes execution and draft publication; neither option authorizes merge, deployment or closure.

## Storage and outcomes

Workflow state uses schema version 3 at `.openfix/workflow/cases.json` by default. It is separate from the legacy Cursor store. Writes are locked across processes, fsynced and atomically renamed. Corruption is surfaced and preserved. Audit hash/checkpoint verification is local integrity checking, not protection against a malicious administrator.

CLI exit codes: 0 for a completed operation, 1 for denied/failed operations or failed patch verification, and 2 for incomplete/inconclusive validation or verification. A disproved finding is a completed investigation, not an execution failure. No case closes because a later scan omits it.
