import test from 'node:test';
import assert from 'node:assert/strict';
import * as w from '../src/lifecycle/workflow.mjs';

const a = { id: 'analyst', role: 'analyst' }, e = { id: 'engineer', role: 'engineer' };
const v = { id: 'verifier', role: 'verifier' }, r = { id: 'reviewer', role: 'reviewer' }, o = { id: 'operator', role: 'operator' };
const base = 'a'.repeat(40), head = 'b'.repeat(40), hash = 'c'.repeat(64);
const candidate = () => w.createCandidate({ id: 'F-1', title: 'Tenant isolation', assetId: 'service:billing', commit: base, severity: 'high', origin: 'simulation' }, a);
const validation = { status: 'confirmed', commit: base, method: 'source', evidence: 'Attacker-controlled ID reaches a lookup without tenant binding.', limitations: ['Runtime reproduction not performed.'] };
const accept = { decision: 'accepted', owner: 'billing', priority: 'P1', reason: 'Tenant isolation is a required invariant.' };
const patch = { baseCommit: base, headCommit: head, sha256: hash, files: ['src/invoice.js'] };
const checks = [{ name: 'security', status: 'passed' }, { name: 'regression', status: 'passed' }];
const verification = { status: 'passed', commit: head, patchHash: hash, checks, limitations: [] };
const accepted = () => w.triageCandidate(w.recordValidation(candidate(), validation, a), accept, r);
const patched = () => w.proposePatch(accepted(), patch, e);
const verified = () => w.recordVerification(patched(), verification, v);
const approved = () => w.reviewPatch(verified(), { decision: 'approved', patchHash: hash, reason: 'Evidence and scope are acceptable.' }, r);

test('candidate cannot skip validation or human acceptance', () => {
  assert.throws(() => w.triageCandidate(candidate(), accept, r), /confirmed/);
  assert.throws(() => w.proposePatch(candidate(), patch, e), /Accepted validation/);
});
test('source-based evidence remains valid with explicit runtime limitations', () => {
  const s = w.recordValidation(candidate(), validation, a);
  assert.equal(w.stageOf(s), 'awaiting_triage');
  assert.equal(s.validation.limitations.length, 1);
});
test('validation for another revision is rejected', () => {
  assert.throws(() => w.recordValidation(candidate(), { ...validation, commit: head }, a), /different source revision/);
});
test('disproved and inconclusive findings have distinct outcomes', () => {
  for (const [status, stage] of [['disproved', 'disproved'], ['inconclusive', 'needs_context']]) {
    const s = w.recordValidation(candidate(), { ...validation, status }, a);
    assert.equal(w.stageOf(s), stage);
    assert.throws(() => w.triageCandidate(s, accept, r), /confirmed/);
  }
});
test('dismissal and deferral require an explanation', () => {
  assert.throws(() => w.triageCandidate(candidate(), { decision: 'dismissed', reason: ' ' }, r), /reason/);
  assert.equal(w.stageOf(w.triageCandidate(candidate(), { decision: 'deferred', reason: 'Missing deployed version mapping.' }, r)), 'deferred');
});
test('patch author cannot impersonate independent verification or approve themselves', () => {
  assert.throws(() => w.recordVerification(patched(), verification, { ...v, id: e.id }), /Patch author/);
  assert.throws(() => w.reviewPatch(verified(), { decision: 'approved', patchHash: hash, reason: 'ok' }, { ...r, id: e.id }), /own patch/);
});
test('only the exact patch and changed revision may be verified', () => {
  assert.throws(() => w.recordVerification(patched(), { ...verification, patchHash: 'd'.repeat(64) }, v), /exact patch/);
  assert.throws(() => w.recordVerification(patched(), { ...verification, commit: base }, v), /exact patch/);
});
test('missing, pending, or failing checks cannot be represented as passed', () => {
  for (const list of [[], [checks[0]], [{ name: 'security', status: 'not_run' }, checks[1]], [{ name: 'security', status: 'failed' }, checks[1]]]) {
    assert.throws(() => w.recordVerification(patched(), { ...verification, checks: list }, v), /cannot pass/);
  }
});
test('failed or incomplete verification blocks approval', () => {
  for (const status of ['failed', 'incomplete']) {
    const s = w.recordVerification(patched(), { ...verification, status }, v);
    assert.throws(() => w.reviewPatch(s, { decision: 'approved', patchHash: hash, reason: 'approve' }, r), /Passing independent/);
  }
});
test('a changed patch invalidates verification, approval, and rollout', () => {
  const original = approved();
  const s = w.proposePatch(original, { ...patch, sha256: 'd'.repeat(64), headCommit: 'e'.repeat(40) }, e);
  assert.equal(w.stageOf(s), 'awaiting_verification');
  assert.equal(s.review, undefined); assert.equal(s.verification, undefined);
  assert.equal(original.review.decision, 'approved');
});
test('safe repository-relative patch paths are required', () => {
  for (const file of ['../outside', '/etc/passwd', '.git/config', 'src\\outside']) {
    assert.throws(() => w.proposePatch(accepted(), { ...patch, files: [file] }, e), /repository-relative/);
  }
});
test('human review can request changes without pretending a failed patch passed', () => {
  const s = w.reviewPatch(patched(), { decision: 'changes_requested', patchHash: hash, reason: 'Add legitimate behavior evidence.' }, r);
  assert.equal(w.stageOf(s), 'changes_requested');
});
test('approval alone never closes the finding', () => {
  assert.equal(w.stageOf(approved()), 'approved_for_change');
  assert.throws(() => w.closeFinding(approved(), 'done', r), /Closure requires/);
});
test('closure requires rollout and post-change revalidation', () => {
  let s = w.recordRollout(approved(), { commit: head, changeRecord: 'CHG-1', merged: true, deployed: true }, o);
  assert.throws(() => w.closeFinding(s, 'done', r), /Closure requires/);
  s = w.recordRevalidation(s, { status: 'passed', commit: head, patchHash: hash, evidence: 'Original failure no longer occurs on deployed artifact.' }, v);
  s = w.closeFinding(s, 'Verified change accepted after rollout.', r);
  assert.equal(w.stageOf(s), 'closed');
  assert.equal(s.events.length, 9);
  assert.equal(w.stageOf(w.reopenFinding(s, 'New bypass reported.', r)), 'candidate');
});
test('unauthorized actor role cannot make a human triage decision', () => {
  assert.throws(() => w.triageCandidate(candidate(), { decision: 'dismissed', reason: 'dismiss' }, e), /not authorized/);
});
test('events and prior states are preserved when a decision changes', () => {
  const start = candidate(); const next = w.recordValidation(start, validation, a);
  assert.equal(start.validation.status, 'not_run');
  assert.equal(start.events.length, 1); assert.equal(next.events.length, 2);
  assert.equal(next.events[1].kind, 'validation_recorded');
});
