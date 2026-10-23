import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { containedFile, digest, immutableRevision, now, redact, repositorySnapshot, stable } from './util.mjs';
import { stageOf } from '../lifecycle/workflow.mjs';
import { event } from './store.mjs';

const CONTEXT_KINDS = ['owner','exposure','criticality','deployedRevision','reachability','exploitability'];
export function freshness(evidence, at = Date.now()) {
  const timestamp = Date.parse(evidence.collectedAt);
  if (!Number.isFinite(timestamp)) return 'unknown';
  if (timestamp > at + 300_000) return 'future';
  const expires = evidence.expiresAt ? Date.parse(evidence.expiresAt) : timestamp + 7 * 86400_000;
  if (!Number.isFinite(expires) || expires <= at) return 'stale';
  return 'fresh';
}
export function addEvidence(c, item) {
  const same = c.evidence.find(e => e.origin === item.origin && e.producer === item.producer && e.kind === item.kind && stable(e.value) === stable(item.value) && e.artifactDigest === item.artifactDigest && freshness(e) === 'fresh');
  if (same) return { reused: true, id: same.id };
  const record = { ...item, id: digest({ ...item, recordedAt: now() }) };
  c.evidence.push(record); return { reused: false, id: record.id };
}
export function factsFor(c, kind) {
  const latest = new Map();
  for (const e of c.evidence.filter(e => e.kind === kind && (!e.revision || e.revision === c.revision) && (!e.repository || e.repository === c.repository) && (!e.assetId || e.assetId === c.assetId))) {
    const key = `${e.origin}:${e.producer}:${kind}`;
    const previous = latest.get(key);
    if (!previous || (Date.parse(e.collectedAt) || 0) >= (Date.parse(previous.collectedAt) || 0)) latest.set(key,e);
  }
  return [...latest.values()];
}
function contextFact(c, kind) {
  const all = factsFor(c,kind), fresh = all.filter(e => freshness(e) === 'fresh');
  const valid = value => kind === 'owner' ? (typeof value === 'string' && value.trim() && value !== 'unknown') || (Array.isArray(value) && value.length && value.every(x=>typeof x==='string'&&x.trim()))
    : kind === 'exposure' ? ['internet','internal','isolated'].includes(value)
    : kind === 'deployedRevision' ? immutableRevision(value)
    : kind === 'criticality' ? ['critical','high','standard','low'].includes(value) : value != null;
  if (fresh.some(e => !valid(e.value))) return { status:'unsupported-or-unknown-value',value:null,evidence:fresh.map(e=>e.id) };
  const values = [...new Set(fresh.map(e => stable(e.value)))];
  if (values.length > 1) return { status: 'conflicting', value: null, evidence: fresh.map(e => e.id) };
  if (values.length === 1) return { status: 'available', value: fresh[0].value, evidence: fresh.map(e => e.id), authority: [...new Set(fresh.map(e => e.authority))] };
  return { status: all.length ? 'stale-or-undated' : 'missing', value: null, evidence: all.map(e => e.id) };
}
export function assessCase(c) {
  const context = Object.fromEntries(CONTEXT_KINDS.map(kind => [kind,contextFact(c,kind)]));
  const gaps = [];
  if(c.observations.some(o=>o.scanContext?.coverage?.deferred?.length))gaps.push('Producer scan has deferred surfaces; completed execution does not mean complete coverage');
  const wrongScope=c.evidence.filter(e=>e.origin==='upstream'&&((e.revision&&e.revision!==c.revision)||(e.repository&&e.repository!==c.repository)||(e.assetId&&e.assetId!==c.assetId))).length;
  if(wrongScope)gaps.push(`${wrongScope} upstream evidence item(s) have a different subject/revision and are excluded from current context`);
  if (!c.repository) gaps.push('Repository identity is missing');
  if (!immutableRevision(c.revision)) gaps.push('Finding revision is not immutable or is missing');
  if (!c.assetId) gaps.push('Asset identity is missing');
  for (const kind of ['owner','exposure']) if (context[kind].status !== 'available') gaps.push(`${kind}: ${context[kind].status}`);
  if (context.deployedRevision.status !== 'available') gaps.push(`Deployed version: ${context.deployedRevision.status}`);
  else if (context.deployedRevision.value !== c.revision) gaps.push('Deployed version differs from finding revision; production applicability is unproven');
  const status = c.lifecycle ? stageOf(c.lifecycle) : 'needs_context';
  if (!c.lifecycle || c.lifecycle.validation.status === 'not_run') gaps.push('No independent validation recorded; producer verdicts remain assertions');
  const evidencePlan = ['owner','exposure','deployedRevision','reachability','exploitability','source_excerpt','validation'].map(kind => {
    const available = factsFor(c,kind), current = available.filter(e => freshness(e) === 'fresh');
    const values = new Set(current.map(e => stable(e.value)));
    return { kind, existing: available.length, upstream: available.filter(e => e.origin === 'upstream').length,
      action: values.size > 1 ? 'resolve-conflict' : kind==='validation'&&current.some(e=>e.origin==='upstream') ? 'review-upstream-validation' : current.length ? 'reuse-with-provenance' : available.length ? 'refresh-or-verify' : 'collect',
      reason: values.size > 1 ? 'Current sources disagree; preserve both' : kind==='validation'&&current.some(e=>e.origin==='upstream') ? 'Check producer method, subject and proof before explicitly adopting its verdict' : current.length ? 'Matching-revision evidence exists; freshness is known, authority is shown separately' : 'Evidence is absent, stale, or undated', evidence: available.map(e => e.id) };
  });
  let score = ({ critical:70, high:50, medium:30, low:10, unknown:20 })[c.severity] || 20;
  const reasons = [`Reported severity ${c.severity}: ${score}`];
  if (context.exposure.value === 'internet') { score += 20; reasons.push('Reported internet exposure: +20'); }
  if (context.criticality.value === 'critical') { score += 15; reasons.push('Business-critical asset: +15'); }
  if (c.lifecycle?.validation.status === 'confirmed') { score += 10; reasons.push('Independent validation recorded: +10'); }
  if (gaps.some(x => /conflict/.test(x))) { score += 5; reasons.push('Conflicting context requires investigation: +5'); }
  const priority = score >= 85 ? 'P0' : score >= 60 ? 'P1' : score >= 35 ? 'P2' : 'P3';
  const contextDigest = digest({ context, brief: c.brief });
  const contextCurrent = c.acceptedContextDigest === contextDigest;
  const remediationAllowed = typeof c.repository==='string' && c.repository.trim() && immutableRevision(c.revision) && c.assetId && c.lifecycle?.validation.status === 'confirmed' && c.lifecycle?.triage.decision === 'accepted' && contextCurrent && context.owner.status === 'available' && context.exposure.status === 'available' && ['sast','sca'].includes(c.category);
  let nextAction = 'Investigate evidence gaps';
  if (status === 'disproved' || status === 'dismissed') nextAction = 'Retain the dismissal evidence; no patch run';
  else if (status === 'needs_context' || status === 'candidate') nextAction = 'Validate against the finding revision';
  else if (status === 'awaiting_triage') nextAction = 'Review evidence, owner and business priority';
  else if (c.lifecycle?.triage.decision === 'accepted' && !contextCurrent) nextAction = 'Context changed or expired; obtain a new acceptance decision';
  else if (status === 'accepted_for_remediation') nextAction = c.category === 'secrets' ? 'Route to credential owner for containment/rotation; no automated patch' : ['sast','sca'].includes(c.category) ? 'Prepare a bounded remediation task' : 'Route to the responsible specialist; this executor supports code/dependency patches';
  else if (status === 'awaiting_verification') nextAction = 'Verify security and legitimate behavior at the exact patch head';
  else if (/verification_|changes_requested/.test(status)) nextAction = 'Revise the patch or resolve incomplete proof';
  else if (status === 'awaiting_human_review') nextAction = 'Review the verified exact patch';
  else if (status === 'approved_for_change') nextAction = 'Use normal publication and deployment controls';
  else if (status === 'closed') nextAction = 'Retain closure evidence and monitor recurrence';
  const effectiveStatus = c.lifecycle?.triage.decision === 'accepted' && !contextCurrent && !c.lifecycle?.closure ? 'needs_reacceptance' : status;
  return { status:effectiveStatus,lifecycleStage:status, context, gaps, evidencePlan, priority: { label: priority, score, reasons, note: 'Priority selects attention; it does not authorize execution.' }, contextDigest, contextCurrent, remediationAllowed: Boolean(remediationAllowed), nextAction };
}
export async function enrichCase(store, id, { manifest, manifestArtifact, repo } = {}) {
  const c = store.cases[id]; if (!c) throw new Error(`Unknown case ${id}`);
  let added = 0, reused = 0;
  const add = item => { const r = addEvidence(c,item); if (r.reused) reused++; else added++; };
  if (manifest) {
    if (manifest.schemaVersion !== 1 || !Array.isArray(manifest.assets)) throw new Error('Asset context requires schemaVersion:1 and assets[]');
    const candidates = manifest.assets.filter(a => a.assetId === c.assetId && a.repository === c.repository && a.revision === c.revision);
    for (const a of candidates) for (const kind of CONTEXT_KINDS) if (a[kind] !== undefined) add({ origin:'enrichment', kind, value:redact(a[kind]), producer:`asset-context:${manifestArtifact.file}`,
      repository:c.repository, revision:c.revision, authority:'context-manifest', collectedAt:a.observedAt || null, expiresAt:a.expiresAt,
      artifactDigest:manifestArtifact.digest, sourceRef:a.evidenceRef || manifestArtifact.file });
    if (!candidates.length) c.lastEnrichmentGap = 'No exact asset/repository/revision match in context manifest';
    else delete c.lastEnrichmentGap;
  }
  if (repo) {
    await repositorySnapshot(repo,c.revision);
    if (c.file) {
      const file = await containedFile(repo,c.file), content = await readFile(file,'utf8');
      if (content.length > 2 * 1024 * 1024) throw new Error('Source file exceeds 2 MiB');
      const lines = content.split('\n'), start = Math.max(0,(c.line || 1)-7);
      add({ origin:'enrichment', kind:'source_excerpt', value:{ file:c.file, startLine:start+1, text:redact(lines.slice(start,start+17).join('\n')) },
        producer:'local-repository', authority:'local-observation', repository:c.repository, revision:c.revision, collectedAt:now(), artifactDigest:digest(content), sourceRef:`${c.revision}:${c.file}` });
    }
    if (c.package?.name) {
      try {
        const lock = JSON.parse(await readFile(await containedFile(repo,'package-lock.json'),'utf8'));
        const installed = lock.packages?.[`node_modules/${c.package.name}`]?.version;
        add({ origin:'enrichment', kind:'dependency_version', value:{ package:c.package.name, observedVersion:installed || null, reportedVersion:c.package.version, reachable:'not-established' },
          producer:'local-lockfile', authority:'local-observation', repository:c.repository, revision:c.revision, collectedAt:now(), artifactDigest:digest(lock) });
      } catch (error) { if (error.code !== 'ENOENT') throw error; }
    }
  }
  c.updatedAt = now(); event(store,'case_enriched',{ id, added, reused, gaps:assessCase(c).gaps }); return { id,added,reused,assessment:assessCase(c) };
}
