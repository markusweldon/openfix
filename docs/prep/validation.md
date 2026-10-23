# Verification of OpenFix 0.2

## Runtime evidence

- `npm test`: 44 passed, zero failed/skipped. `npm run typecheck` and `npm run build` passed.
- The primary CLI imports multiple source formats and uses the lifecycle domain on persistent cases. Separate-process CLI checks verify import and report behavior across restarts.
- The integrated demo retains five observations in four cases and five attempted validation/verification runs. Four reference probes actually execute; one unavailable profile remains inconclusive.
- A cross-tenant lookup is reproduced. A protected lookup is disproved. Conflicting ownership remains visible. A deny-all patch fails legitimate behavior and cannot approve; the corrected patch passes at its actual Git head and diff digest.
- Software checks cover producer self-confirmation, wrong-subject evidence, stale/undated context, conflicts, missing runtime capability, atomic storage, writer contention, corruption, unsafe source paths, unsafe HTML embedding, exact artifacts and review/closure gates.
- TypeScript checking and build cover the retained Cursor adapter. Invalid legacy policy and corrupt legacy state were checked directly and preserve the original data.

## Visual and documentation checks

The workbench uses current persisted case data and supports read-only case selection, filtering and evidence inspection. Chromium checks selected all four cases, filtered to the inconclusive dependency and conflicting-owner cases, and reported no JavaScript errors. The recorded HTML contains only reference-demo data.

The revised purple deck has 16 slides, 16 speaker notes and 16 exported PDF pages. Rendered contact-sheet and dense-slide inspection found no visible overflow; PDF text spans remain within page bounds. It embeds the actual workbench screenshot. Main body text contrast is at least 14.37:1. Mermaid, SVG and PNG sources describe the same implemented architecture and gates. The editable whiteboard validates with 58 elements, 17 prompts and no external assets.

## Limits

No live scanner, model request, Cursor job, production deployment or customer outcome is claimed. The Codex Security JSON adapter is checked against the documented wrapper/fields and synthetic contract fixtures; it does not authenticate a Cloud export or establish a live integration.

The local tenant probe is a narrow reference check in a bounded process, not a container/network sandbox. Local actor names and roles are caller assertions. Production use needs isolated execution, authenticated actor/tenant/action authorization, trusted evidence ingestion and external audit. The casebook and fixture tests do not establish vulnerability detection accuracy, model quality or production ROI.
