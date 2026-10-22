/**
 * OpenFix lifecycle domain prototype. No model, network, or deployment calls.
 * Actor roles are assertions supplied by the caller; a production service must
 * authenticate them. Evidence is recorded, not independently authenticated here.
 */
const SHA = /^[a-f0-9]{40,64}$/i;
const HASH = /^[a-f0-9]{64}$/i;
const requireValue = (condition, message) => { if (!condition) throw new Error(message); };
const text = (value) => typeof value === 'string' && value.trim().length > 0;
const reasonRequired = (reason) => requireValue(text(reason), 'A specific decision reason is required');

function authorize(actor, roles) {
  requireValue(text(actor?.id) && roles.includes(actor?.role), 'Actor role is not authorized for this decision');
}
function event(state, actor, kind, detail) {
  const next = structuredClone(state);
  next.events.push({ sequence: next.events.length + 1, at: new Date().toISOString(), actor: structuredClone(actor), kind, detail: structuredClone(detail) });
  return next;
}
function currentValidation(state) {
  return state.validation.status === 'confirmed' && state.validation.commit === state.commit;
}
function verified(state) {
  return state.patch && state.verification?.status === 'passed' &&
    state.verification.patchHash === state.patch.sha256 && state.verification.commit === state.patch.headCommit;
}
function approved(state) {
  return state.patch && state.review?.decision === 'approved' && state.review.patchHash === state.patch.sha256;
}
function clearPatchDecisions(state) {
  delete state.verification; delete state.review; delete state.rollout; delete state.revalidation; delete state.closure;
}

export function createCandidate(input, actor) {
  authorize(actor, ['analyst', 'automation']);
  requireValue(text(input.id) && text(input.title) && text(input.assetId) && SHA.test(input.commit), 'Candidate needs identity, title, asset, and immutable commit');
  requireValue(['codex-security', 'scanner', 'manual', 'simulation'].includes(input.origin), 'Unknown finding origin');
  requireValue(['critical', 'high', 'medium', 'low', 'unknown'].includes(input.severity), 'Unknown severity');
  const requiredChecks = input.requiredChecks || ['security', 'regression'];
  requireValue(Array.isArray(requiredChecks) && requiredChecks.length > 0 && requiredChecks.every(text), 'Required verification checks must be explicit');
  const state = {
    schemaVersion: 2, id: input.id, title: input.title, assetId: input.assetId,
    commit: input.commit, origin: input.origin, severity: input.severity,
    requiredChecks: [...new Set(requiredChecks)], context: structuredClone(input.context || []),
    validation: { status: 'not_run' }, triage: { decision: 'unreviewed' }, events: [],
  };
  return event(state, actor, 'candidate_created', { origin: input.origin, commit: input.commit });
}

export function recordValidation(state, result, actor) {
  authorize(actor, ['analyst', 'automation', 'verifier']);
  requireValue(!state.closure, 'Reopen the finding before changing a closed decision');
  requireValue(['confirmed', 'disproved', 'inconclusive'].includes(result.status), 'Unknown validation status');
  requireValue(result.commit === state.commit, 'Validation is for a different source revision');
  requireValue(['runtime', 'source', 'simulation'].includes(result.method), 'Validation method must be explicit');
  requireValue(text(result.evidence) && Array.isArray(result.limitations) && result.limitations.every(text), 'Validation requires evidence and explicit limitations');
  const next = event(state, actor, 'validation_recorded', result);
  next.validation = structuredClone(result);
  next.triage = { decision: 'unreviewed' };
  delete next.patch; clearPatchDecisions(next);
  return next;
}

export function triageCandidate(state, decision, actor) {
  authorize(actor, ['reviewer']); reasonRequired(decision.reason);
  requireValue(!state.closure, 'Reopen the finding before changing a closed decision');
  requireValue(['accepted', 'deferred', 'dismissed'].includes(decision.decision), 'Unknown triage decision');
  if (decision.decision === 'accepted') {
    requireValue(currentValidation(state), 'Only a confirmed finding at the current source revision can be accepted');
    requireValue(text(decision.owner) && ['P0', 'P1', 'P2', 'P3'].includes(decision.priority), 'Acceptance requires owner and explicit priority');
  }
  const next = event(state, actor, 'triage_decided', decision);
  next.triage = { ...structuredClone(decision), actor: structuredClone(actor) };
  delete next.patch; clearPatchDecisions(next);
  return next;
}

export function proposePatch(state, patch, actor) {
  authorize(actor, ['engineer', 'automation']);
  requireValue(!state.closure && currentValidation(state) && state.triage.decision === 'accepted', 'Accepted validation is required before patching');
  requireValue(patch.baseCommit === state.commit && SHA.test(patch.headCommit) && patch.headCommit !== patch.baseCommit, 'Patch must bind its original and changed revisions');
  requireValue(HASH.test(patch.sha256), 'Patch requires a SHA-256 identity');
  requireValue(Array.isArray(patch.files) && patch.files.length > 0 && patch.files.every((file) => text(file) && !file.startsWith('/') && !file.includes('\\') && !file.split('/').includes('..') && file !== '.git' && !file.startsWith('.git/')), 'Patch files must be safe repository-relative paths');
  const next = event(state, actor, 'patch_proposed', patch);
  next.patch = { ...structuredClone(patch), author: structuredClone(actor) };
  clearPatchDecisions(next);
  return next;
}

export function recordVerification(state, result, actor) {
  authorize(actor, ['verifier']);
  requireValue(state.patch && !state.closure, 'An open patch is required for verification');
  requireValue(actor.id !== state.patch.author.id, 'Patch author cannot supply independent verification');
  requireValue(result.patchHash === state.patch.sha256 && result.commit === state.patch.headCommit, 'Verification does not match the exact patch and revision');
  requireValue(['passed', 'failed', 'incomplete'].includes(result.status), 'Unknown verification status');
  requireValue(Array.isArray(result.checks) && result.checks.every((check) => text(check.name) && ['passed', 'failed', 'not_run'].includes(check.status)), 'Checks need explicit names and outcomes');
  requireValue(Array.isArray(result.limitations) && result.limitations.every(text), 'Verification limitations must be explicit');
  if (result.status === 'passed') {
    requireValue(result.checks.length > 0 && result.checks.every((check) => check.status === 'passed') &&
      state.requiredChecks.every((name) => result.checks.some((check) => check.name === name && check.status === 'passed')),
    'Missing, pending, skipped, or failed required checks cannot pass verification');
  }
  const next = event(state, actor, 'verification_recorded', result);
  next.verification = { ...structuredClone(result), actor: structuredClone(actor) };
  delete next.review; delete next.rollout; delete next.revalidation; delete next.closure;
  return next;
}

export function reviewPatch(state, review, actor) {
  authorize(actor, ['reviewer']); reasonRequired(review.reason);
  requireValue(state.patch && !state.closure && review.patchHash === state.patch.sha256, 'Review must identify an open, exact patch');
  requireValue(actor.id !== state.patch.author.id, 'Patch author cannot approve their own patch');
  requireValue(['approved', 'changes_requested'].includes(review.decision), 'Unknown review decision');
  if (review.decision === 'approved') requireValue(verified(state), 'Passing independent verification is required before approval');
  const next = event(state, actor, 'patch_reviewed', review);
  next.review = { ...structuredClone(review), actor: structuredClone(actor) };
  delete next.rollout; delete next.revalidation; delete next.closure;
  return next;
}

export function recordRollout(state, result, actor) {
  authorize(actor, ['operator']);
  requireValue(!state.closure && verified(state) && approved(state), 'Verified approval is required before recording rollout');
  requireValue(result.commit === state.patch.headCommit && text(result.changeRecord), 'Rollout requires the reviewed revision and a change record');
  requireValue(result.merged === true && result.deployed === true, 'Both merge and deployment must be recorded');
  const next = event(state, actor, 'rollout_recorded', result);
  next.rollout = structuredClone(result); delete next.revalidation; delete next.closure;
  return next;
}

export function recordRevalidation(state, result, actor) {
  authorize(actor, ['verifier']);
  requireValue(state.rollout && !state.closure, 'A recorded rollout is required before post-change validation');
  requireValue(result.commit === state.patch.headCommit && result.patchHash === state.patch.sha256, 'Revalidation is for a different deployed artifact');
  requireValue(['passed', 'failed', 'incomplete'].includes(result.status) && text(result.evidence), 'Revalidation requires a result and evidence');
  const next = event(state, actor, 'revalidation_recorded', result);
  next.revalidation = structuredClone(result);
  return next;
}

export function closeFinding(state, reason, actor) {
  authorize(actor, ['reviewer']); reasonRequired(reason);
  requireValue(!state.closure && verified(state) && approved(state) && state.rollout && state.revalidation?.status === 'passed', 'Closure requires verified approval, rollout, and successful revalidation');
  const next = event(state, actor, 'finding_closed', { reason });
  next.closure = { reason, actor: structuredClone(actor), at: new Date().toISOString() };
  return next;
}

export function reopenFinding(state, reason, actor) {
  authorize(actor, ['reviewer']); reasonRequired(reason);
  requireValue(state.closure, 'Only a closed finding can be reopened');
  const next = event(state, actor, 'finding_reopened', { reason });
  next.validation = { status: 'not_run' }; next.triage = { decision: 'unreviewed' };
  delete next.patch; clearPatchDecisions(next);
  return next;
}

export function stageOf(state) {
  if (state.closure) return 'closed';
  if (state.revalidation?.status === 'failed') return 'revalidation_failed';
  if (state.rollout) return 'awaiting_revalidation';
  if (approved(state)) return 'approved_for_change';
  if (state.review?.decision === 'changes_requested') return 'changes_requested';
  if (verified(state)) return 'awaiting_human_review';
  if (state.verification) return state.verification.status === 'failed' ? 'verification_failed' : 'verification_incomplete';
  if (state.patch) return 'awaiting_verification';
  if (state.triage.decision === 'accepted') return 'accepted_for_remediation';
  if (state.triage.decision === 'dismissed') return 'dismissed';
  if (state.triage.decision === 'deferred') return 'deferred';
  if (state.validation.status === 'disproved') return 'disproved';
  if (state.validation.status === 'inconclusive') return 'needs_context';
  if (currentValidation(state)) return 'awaiting_triage';
  return 'candidate';
}
