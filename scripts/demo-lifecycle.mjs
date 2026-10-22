import { writeFile } from 'node:fs/promises';
import { createCandidate, recordValidation, triageCandidate, proposePatch, recordVerification, reviewPatch, recordRollout, recordRevalidation, closeFinding, stageOf } from '../src/lifecycle/workflow.mjs';

const analyst = { id: 'demo-analyst', role: 'analyst' };
const engineer = { id: 'demo-engineer', role: 'engineer' };
const verifier = { id: 'demo-verifier', role: 'verifier' };
const reviewer = { id: 'demo-reviewer', role: 'reviewer' };
const operator = { id: 'demo-operator', role: 'operator' };
const base = 'a'.repeat(40), head = 'b'.repeat(40), patchHash = 'c'.repeat(64);
let state = createCandidate({ id: 'DEMO-001', title: 'Cross-tenant invoice access', assetId: 'service:billing-api', commit: base, origin: 'simulation', severity: 'high' }, analyst);
console.log('OPENFIX · lifecycle simulation · no model, scan, merge, or deployment is executed');
const show = () => console.log(`${String(state.events.length).padStart(2, '0')}  ${stageOf(state)}`);
show();
state = recordValidation(state, { status: 'confirmed', commit: base, method: 'simulation', evidence: 'Simulated reproducer: a tenant reads another tenant invoice.', limitations: ['Fabricated evidence for a workflow demonstration.'] }, analyst); show();
state = triageCandidate(state, { decision: 'accepted', priority: 'P1', owner: 'billing-team', reason: 'Hypothetical customer impact and tenant boundary justify a focused fix.' }, reviewer); show();
state = proposePatch(state, { baseCommit: base, headCommit: head, sha256: patchHash, files: ['src/invoices.mjs'], summary: 'Simulated tenant ownership predicate.' }, engineer); show();
state = recordVerification(state, { status: 'passed', commit: head, patchHash, checks: [{ name: 'security', status: 'passed' }, { name: 'regression', status: 'passed' }], limitations: ['Simulation, not executed tests.'] }, verifier); show();
state = reviewPatch(state, { decision: 'approved', patchHash, reason: 'Simulated independent review accepts the exact artifact.' }, reviewer); show();
state = recordRollout(state, { commit: head, changeRecord: 'SIMULATED-CHANGE-001', merged: true, deployed: true }, operator); show();
state = recordRevalidation(state, { status: 'passed', commit: head, patchHash, evidence: 'Simulated post-change check; no deployment actually occurred.' }, verifier); show();
state = closeFinding(state, 'Simulated closure after all modeled gates.', reviewer); show();
const outIndex = process.argv.indexOf('--out');
if (outIndex !== -1) {
  const target = process.argv[outIndex + 1];
  if (!target) throw new Error('--out requires a new file path');
  await writeFile(target, JSON.stringify(state, null, 2) + '\n', { flag: 'wx', mode: 0o600 });
  console.log(`Simulation record: ${target}`);
}
