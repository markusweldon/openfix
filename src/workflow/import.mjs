import { digest, invariant, immutableRevision, now, redact } from './util.mjs';
import { createCandidate } from '../lifecycle/workflow.mjs';
import { event } from './store.mjs';

function severity(value, score) {
  if (score != null && Number.isFinite(Number(score))) return Number(score) >= 9 ? 'critical' : Number(score) >= 7 ? 'high' : Number(score) >= 4 ? 'medium' : 'low';
  const v = String(value || 'unknown').toLowerCase();
  return ({ error: 'high', warning: 'medium', note: 'low', info: 'low', none: 'low' })[v] || (['critical','high','medium','low'].includes(v) ? v : 'unknown');
}
function category(value, text) {
  if (['sast','sca','secrets','iac','cloud','runtime','other'].includes(value)) return value;
  return /secret|credential/i.test(text) ? 'secrets' : /CVE-|GHSA-|dependency/i.test(text) ? 'sca' : 'sast';
}
function upstreamClaims(raw) {
  const claims = [];
  const add = (kind, value, at, meta={}) => { if (value !== undefined && value !== null) {
    const nested=value&&typeof value==='object'&&!Array.isArray(value)?value:{};
    claims.push({ kind, value: redact(value), collectedAt:nested.collectedAt || nested.observedAt || at || null,
      revision:meta.revision || meta.commit || nested.revision || nested.commit,repository:meta.repository || nested.repository,assetId:meta.assetId || nested.assetId,
      expiresAt:meta.expiresAt || nested.expiresAt,sourceRef:meta.sourceRef || nested.sourceRef,authority:'upstream-assertion' });
  }};
  for (const e of Array.isArray(raw.evidence) ? raw.evidence : []) add(e.kind || e.type || 'producer-evidence', e.value ?? e.summary ?? e, e.collectedAt || e.observedAt,e);
  const context = [raw.enrichment, raw.properties?.enrichment, raw.context].filter(x => x && typeof x === 'object' && !Array.isArray(x));
  for (const c of context) for (const [key,value] of Object.entries(c)) if(!['observedAt','collectedAt','revision','commit','repository','assetId','expiresAt','sourceRef'].includes(key))add(key, value, c.observedAt || c.collectedAt,c);
  for (const source of [raw,raw.properties||{}])for (const key of ['reachability','validation','exploitability','exposure','owner','runtimeEvidence','codeEvidence','rootCause','attackPath','remediationTests','preventiveControls','dismissed','state']) add(key, source[key], source.observedAt || raw.updated_at,source);
  return claims;
}
function observation(raw, fields, envelope, artifact) {
  const repository = fields.repository || envelope.repository || null;
  const revision = fields.revision || envelope.revision || null;
  const assetId = fields.assetId || envelope.assetId || repository || null;
  const producer = fields.producer || envelope.producer || 'unknown';
  const result = { producer, sourceId: String(fields.sourceId || digest(raw).slice(0,16)), repository, revision, assetId,
    title: String(fields.title || 'Imported finding'), ruleId: String(fields.ruleId || 'unknown'), severity: severity(fields.severity,fields.score),
    category: category(fields.category, `${fields.ruleId} ${fields.title}`), file: fields.file || null, line: fields.line || null,
    cwe: typeof fields.cwe==='string' ? (fields.cwe.match(/CWE-\d+/i)?.[0].toUpperCase() || fields.cwe) : null, package: fields.package || null, advisory: fields.advisory || null,
    claims: upstreamClaims(raw), original: redact(raw), artifactDigest: artifact.digest, artifactPath: artifact.file,
    observedAt: fields.observedAt || envelope.observedAt || null, importedAt: now() };
  result.id = digest({ artifact: artifact.digest, producer, sourceId: result.sourceId, raw });
  return redact(result);
}
export function normalizeDocument(document, options, artifact) {
  invariant(document && typeof document === 'object', 'A finding document must be a JSON object or array');
  const envelope = { repository: typeof document.repository==='string'?document.repository:options.repository, revision: document.revision || options.revision,
    assetId: document.assetId || options.assetId, producer: typeof document.producer === 'string' ? document.producer : document.producer?.name || document.source,
    observedAt: document.observedAt };
  const out = [], push = (raw,fields,e = envelope) => out.push(observation(raw,fields,e,artifact));
  let format,metadata={};
  if(document.manifest && Array.isArray(document.findings?.findings)) {
    format='codex-security-scan-json';
    metadata=redact({manifest:document.manifest,coverage:document.coverage,turn:document.turn,cost:document.cost,repositoryFindings:document.repositoryFindings});
    for(const f of document.findings.findings)push(f,{producer:'Codex Security',sourceId:f.id||f.findingId,ruleId:f.ruleId||f.cwe||'codex-security-finding',
      title:f.title,severity:f.severity?.level,file:f.locations?.[0]?.path,line:f.locations?.[0]?.startLine,cwe:f.cwe,category:'sast'});
  } else if (Array.isArray(document.runs)) {
    format = 'sarif';
    for (const run of document.runs) {
      const driver = run.tool?.driver || {}, provenance = run.versionControlProvenance?.[0] || {};
      for (const [i,result] of (run.results || []).entries()) {
        const rule = driver.rules?.find(r => r.id === result.ruleId) || {}, properties = { ...rule.properties, ...result.properties };
        const location = result.locations?.[0]?.physicalLocation;
        push(result, { producer: driver.name, sourceId: result.guid || `${result.ruleId}:${i}`, title: result.message?.text || rule.shortDescription?.text,
          ruleId: result.ruleId, severity: result.level || rule.defaultConfiguration?.level, score: properties['security-severity'] || properties.security_severity,
          file: location?.artifactLocation?.uri, line: location?.region?.startLine, category: properties.category,
          cwe: properties.cwe || properties.tags?.find(t => /cwe-\d+/i.test(t)), repository: provenance.repositoryUri, revision: provenance.revisionId,
          observedAt: result.properties?.observedAt });
      }
    }
  } else if ((Array.isArray(document) && document.some(x => x.most_recent_instance)) || Array.isArray(document.alerts)) {
    format = 'github-code-scanning';
    for (const a of Array.isArray(document) ? document : document.alerts) {
      const instance = a.most_recent_instance || {};
      push(a,{ producer: a.tool?.name || 'github-code-scanning', sourceId: a.number, ruleId: a.rule?.id, title: a.rule?.description || instance.message?.text,
        severity: a.rule?.security_severity_level || a.rule?.severity, file: instance.location?.path, line: instance.location?.start_line,
        cwe: a.rule?.tags?.find(t => /cwe-\d+/i.test(t)), revision: instance.commit_sha, repository: a.repository?.html_url });
    }
  } else if (Array.isArray(document.vulnerabilities)) {
    format = 'snyk';
    for (const v of document.vulnerabilities) push(v,{ producer: 'snyk', sourceId: v.id, ruleId: v.id, title: v.title, severity: v.severity,
      category: 'sca', package: { name: v.packageName || v.name, version: v.version }, advisory: v.identifiers?.CVE?.[0] || v.id,
      file: document.targetFile || 'package.json', cwe: v.identifiers?.CWE?.[0] });
  } else if (Array.isArray(document.findings)) {
    invariant(document.schemaVersion === 2 || document.version === 1,'Finding envelopes require schemaVersion:2 or legacy version:1; unsupported schemas are not guessed');
    format = document.schemaVersion === 2 ? 'openfix-v2' : 'findings-json';
    for (const f of document.findings) push(f,{ ...f, producer: f.tool || f.producer || envelope.producer,
      sourceId: f.id || f.fingerprint, ruleId: f.ruleId || f.rule_id || f.id, title: f.title || f.message,
      file: f.file || f.location?.path, line: f.startLine || f.line || f.location?.line, revision: f.revision || f.commit,
      package: f.package, advisory: f.advisory });
  } else throw new Error('Unsupported finding document. Use SARIF, GitHub code-scanning alerts, Snyk JSON, or an OpenFix v2 findings envelope.');
  invariant(out.length <= 5000, 'Import exceeds 5000 findings');
  return { format, observations: out,metadata };
}
export function caseKey(obs) {
  // Grouping suggests one investigation; it never confirms equivalence or validity.
  if (!obs.repository || !immutableRevision(obs.revision) || !obs.assetId) return digest({ unscopedObservation: obs.id });
  if (obs.category === 'sast' && (!obs.file || !Number.isInteger(obs.line))) return digest({ insufficientLocation: obs.id });
  return digest({ repository: obs.repository, revision: obs.revision, assetId: obs.assetId, file: obs.file,
    line: obs.line, identity: obs.package ? `${obs.package.name}@${obs.package.version}:${obs.advisory || obs.ruleId}` : (obs.cwe || obs.ruleId).toUpperCase(), category: obs.category });
}
export function importObservations(store, normalized, artifact, brief = {}) {
  let added = 0, reused = 0; const touched = new Set();
  store.artifacts[artifact.digest] = { sha256: artifact.digest, file: artifact.file, format: normalized.format, metadata:normalized.metadata, importedAt: now() };
  for (const obs of normalized.observations) {
    if(normalized.format==='codex-security-scan-json')obs.scanContext={status:normalized.metadata.manifest?.scan?.status,coverage:normalized.metadata.coverage};
    const key = caseKey(obs), id = `OF-${key.slice(0,12).toUpperCase()}`;
    let c = store.cases[id];
    if (!c) {
      c = store.cases[id] = { id, correlationKey: key, title: obs.title, repository: obs.repository, revision: obs.revision,
        assetId: obs.assetId, file: obs.file, line: obs.line, category: obs.category, severity: obs.severity, cwe: obs.cwe,
        package: obs.package, brief: redact(brief), observations: [], evidence: [], context: {}, gaps: [], createdAt: now() };
      if (immutableRevision(obs.revision) && obs.assetId) c.lifecycle = createCandidate({ id, title: c.title, assetId: c.assetId, commit: c.revision, origin: 'scanner', severity: c.severity }, { id: 'import-adapter', role: 'automation' });
    }
    touched.add(id);
    if (c.observations.some(o => o.id === obs.id)) { reused++; continue; }
    c.observations.push(obs); added++;
    for (const claim of obs.claims) c.evidence.push({ ...claim, id: digest({ observation: obs.id, claim }), observationId: obs.id,
      producer: obs.producer, repository: claim.repository || obs.repository, revision: claim.revision || obs.revision,assetId:claim.assetId || obs.assetId, artifactDigest: obs.artifactDigest, origin: 'upstream' });
    const rank = ['critical','high','medium','low','unknown'];
    if (rank.indexOf(obs.severity) < rank.indexOf(c.severity)) c.severity = obs.severity;
  }
  event(store, 'findings_imported', { artifact: artifact.digest, format: normalized.format, added, reused, cases: [...touched] });
  return { added, reused, cases: [...touched] };
}
