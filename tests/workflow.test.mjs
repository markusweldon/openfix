import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, readFile, writeFile, symlink, mkdir } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { digest, jsonFile, now, exec } from '../src/workflow/util.mjs';
import { emptyStore, loadStore, mutateStore, event } from '../src/workflow/store.mjs';
import { normalizeDocument, importObservations, caseKey } from '../src/workflow/import.mjs';
import { assessCase, enrichCase, freshness } from '../src/workflow/enrich.mjs';
import { validateCase, decideCase, reviewCase, closeCase } from '../src/workflow/operations.mjs';
import { renderReport } from '../src/workflow/report.mjs';
import { runDemo, fixtureRepo } from '../src/workflow/demo.mjs';
import { dispatchCursor } from '../src/workflow/providers.mjs';

const revision='a'.repeat(40),repository='https://example.invalid/org/repo',assetId='service:api';
const artifact={digest:'b'.repeat(64),file:'/tmp/input.json'};
const baseDoc=()=>({schemaVersion:2,producer:'scanner-a',repository,revision,assetId,findings:[{id:'f1',ruleId:'tenant-check',title:'Tenant boundary',category:'sast',cwe:'CWE-639',file:'src/invoices.mjs',line:3,severity:'high'}]});
function imported(document=baseDoc(),file=artifact){const store=emptyStore();const normalized=normalizeDocument(document,{},file);const result=importObservations(store,normalized,file);return {store,c:store.cases[result.cases[0]],result,normalized};}
function context(owner='billing-team',observedAt=now()){return {schemaVersion:1,assets:[{assetId,repository,revision,owner,exposure:'internet',deployedRevision:revision,criticality:'critical',observedAt}]};}

test('reference validation cannot confirm an unrelated finding in the same repository',async()=>{
 const repo=await mkdtemp(path.join(os.tmpdir(),'openfix-profile-scope-')),head=await fixtureRepo(repo);
 for(const change of [{category:'sca',file:'package.json'},{cwe:'CWE-89'},{line:30},{file:'src/other.mjs'}]){
  const doc=baseDoc();doc.revision=head;Object.assign(doc.findings[0],change);const {store,c}=imported(doc);
  const result=await validateCase(store,c.id,{repo,profile:'tenant-isolation',execute:true});
  assert.equal(result.verdict,'inconclusive');assert.equal(result.run.status,'incomplete');assert.match(result.run.error,/outside its evidence scope/);assert.equal(c.runs.length,1);
 }
});
test('Cursor cannot publish a draft PR through execution consent alone',async()=>{
 const {store,c}=imported();await assert.rejects(()=>dispatchCursor(store,c.id,{execute:true,actor:'operator'}),/authorize publication separately/);
 assert.equal(c.executorJobs,undefined);
});
test('missing repository identity cannot acquire validation or acceptance authority',async()=>{
 const doc=baseDoc();delete doc.repository;const {store,c}=imported(doc);
 await assert.rejects(()=>validateCase(store,c.id,{attest:true,actor:'analyst',evidence:{revision,method:'source',verdict:'confirmed',summary:'trace',limitations:[]}}),/needs a repository/);
 assert.throws(()=>decideCase(store,c.id,{actor:'reviewer',owner:'team',reason:'try'}),/needs a repository/);
 assert.equal(assessCase(c).remediationAllowed,false);
});

test('producer-enriched findings keep original provenance and cannot self-confirm',()=>{
 const doc=baseDoc();doc.findings[0].validation={status:'confirmed',method:'runtime'};doc.findings[0].enrichment={reachability:true,owner:'billing-team',observedAt:now()};
 const {c}=imported(doc);assert.equal(c.observations[0].original.validation.status,'confirmed');assert.equal(c.lifecycle.validation.status,'not_run');assert.equal(c.evidence.find(e=>e.kind==='reachability').authority,'upstream-assertion');assert.equal(assessCase(c).remediationAllowed,false);
});
test('matching scoped observations group without discarding source disagreement',()=>{
 const {store,c}=imported();const doc=baseDoc();doc.producer='scanner-b';doc.findings[0].id='other-id';doc.findings[0].enrichment={reachability:false,observedAt:now()};const other={...artifact,digest:'c'.repeat(64)};
 importObservations(store,normalizeDocument(doc,{},other),other);assert.equal(Object.keys(store.cases).length,1);assert.equal(c.observations.length,2);assert.equal(c.observations[1].producer,'scanner-b');
});
test('reimport is idempotent for observations and evidence',()=>{
 const {store,c,normalized}=imported();const result=importObservations(store,normalized,artifact);assert.equal(result.added,0);assert.equal(result.reused,1);assert.equal(c.observations.length,1);
});
test('Codex Security scan JSON preserves documented findings, coverage and upstream proof',()=>{
 const doc={manifest:{scan:{status:'completed'}},coverage:{deferred:[{id:'runtime',reason:'Environment unavailable'}]},findings:{findings:[{id:'codex-1',title:'Candidate from native scan',severity:{level:'high'},locations:[{path:'src/invoices.mjs',startLine:3}],validation:{status:'confirmed',observedAt:now()},codeEvidence:{summary:'source trace'}}]}};
 const normalized=normalizeDocument(doc,{repository,revision,assetId},artifact),store=emptyStore();const importedResult=importObservations(store,normalized,artifact);const c=store.cases[importedResult.cases[0]];
 assert.equal(normalized.format,'codex-security-scan-json');assert.equal(c.severity,'high');assert.equal(c.lifecycle.validation.status,'not_run');assert.equal(store.artifacts[artifact.digest].metadata.coverage.deferred[0].id,'runtime');assert.ok(c.evidence.some(e=>e.kind==='codeEvidence'));
});
test('older-revision upstream enrichment is preserved but excluded from current context',()=>{
 const doc=baseDoc();doc.findings[0].evidence=[{kind:'owner',value:'old-owner',revision:'f'.repeat(40),collectedAt:now()}];const {c}=imported(doc);assert.equal(c.evidence[0].revision,'f'.repeat(40));assert.equal(assessCase(c).context.owner.status,'missing');assert.match(assessCase(c).gaps.join(' '),/different subject\/revision/);
});
test('empty later scan is retained without closing earlier findings',()=>{
 const {store,c}=imported();const empty={version:'2.1.0',runs:[]},a={digest:'e'.repeat(64),file:'/tmp/empty.sarif'};const result=importObservations(store,normalizeDocument(empty,{},a),a);assert.equal(result.added,0);assert.equal(Object.keys(store.artifacts).length,2);assert.equal(c.lifecycle.validation.status,'not_run');assert.equal(c.lifecycle.closure,undefined);
});
test('recognized credential values are redacted from title as well as raw payload',()=>{
 const doc=baseDoc();doc.findings[0].title='Secret sk-proj-'+ 'a'.repeat(40);const {c}=imported(doc);assert.ok(!JSON.stringify(c).includes('sk-proj-'));assert.match(c.title,/REDACTED/);
});
test('correlation never crosses repository, revision, asset or code location',()=>{
 const obs=imported().normalized.observations[0],key=caseKey(obs);
 for(const change of [{repository:'https://example.invalid/another/repo'},{revision:'d'.repeat(40)},{assetId:'other'},{line:90}])assert.notEqual(caseKey({...obs,...change}),key);
});
test('unversioned or insufficiently located reports stay separate and cannot acquire authority',()=>{
 const a=imported().normalized.observations[0];assert.notEqual(caseKey({...a,id:'one',revision:null}),caseKey({...a,id:'two',revision:null}));assert.notEqual(caseKey({...a,id:'one',line:null}),caseKey({...a,id:'two',line:null}));
 const doc=baseDoc();delete doc.revision;const {c}=imported(doc);assert.equal(c.lifecycle,undefined);assert.match(assessCase(c).gaps.join(' '),/immutable/);
});
test('Snyk reachability evidence is preserved rather than inferred from severity',()=>{
 const doc={repository,revision,assetId,vulnerabilities:[{id:'issue',title:'dependency issue',packageName:'demo',version:'1.0',severity:'high',enrichment:{reachability:false,observedAt:now()}}]};
 const {c}=imported(doc);assert.equal(c.package.name,'demo');assert.equal(c.evidence.find(e=>e.kind==='reachability').value,false);assert.equal(assessCase(c).evidencePlan.find(p=>p.kind==='reachability').action,'reuse-with-provenance');assert.equal(c.lifecycle.validation.status,'not_run');
});
test('current conflicting ownership remains visible and blocks acceptance',async()=>{
 const doc=baseDoc();doc.findings[0].enrichment={owner:'team-a',observedAt:now()};const {store,c}=imported(doc);
 await enrichCase(store,c.id,{manifest:context('team-b'),manifestArtifact:artifact});assert.equal(assessCase(c).context.owner.status,'conflicting');assert.throws(()=>decideCase(store,c.id,{actor:'reviewer',owner:'team-b',reason:'try acceptance'}),/nonconflicting/);
});
test('stale, future and unknown evidence is not silently freshened by import',async()=>{
 assert.equal(freshness({collectedAt:'2000-01-01'}),'stale');assert.equal(freshness({collectedAt:'2999-01-01'}),'future');assert.equal(freshness({}),'unknown');
 const {store,c}=imported();await enrichCase(store,c.id,{manifest:context('billing-team','2000-01-01'),manifestArtifact:artifact});assert.equal(assessCase(c).context.owner.status,'stale-or-undated');
});
test('unknown or malformed owner/exposure values cannot satisfy context gates',async()=>{
 const {store,c}=imported();const m=context();m.assets[0].owner=true;m.assets[0].exposure='unknown';await enrichCase(store,c.id,{manifest:m,manifestArtifact:artifact});assert.equal(assessCase(c).context.owner.status,'unsupported-or-unknown-value');assert.equal(assessCase(c).remediationAllowed,false);
});
test('asset enrichment requires the exact asset, repository and revision join',async()=>{
 const {store,c}=imported(),m=context();m.assets[0].revision='e'.repeat(40);await enrichCase(store,c.id,{manifest:m,manifestArtifact:artifact});assert.equal(c.evidence.length,0);assert.match(c.lastEnrichmentGap,/exact/);
});
test('re-enrichment reuses matching current evidence and never validates a finding',async()=>{
 const {store,c}=imported(),m=context();await enrichCase(store,c.id,{manifest:m,manifestArtifact:artifact});const again=await enrichCase(store,c.id,{manifest:m,manifestArtifact:artifact});assert.equal(again.added,0);assert.equal(again.reused,4);assert.equal(c.lifecycle.validation.status,'not_run');
});
test('missing runtime capability is inconclusive and retained in attempted runs',async()=>{
 const {store,c}=imported();const result=await validateCase(store,c.id,{profile:'not-installed',execute:true});assert.equal(result.verdict,'inconclusive');assert.equal(c.runs.length,1);assert.equal(c.runs[0].status,'incomplete');assert.throws(()=>decideCase(store,c.id,{actor:'reviewer',owner:'team',reason:'try'}));
});
test('external verdicts require explicit attestation and immutable evidence scope',async()=>{
 const {store,c}=imported();await assert.rejects(()=>validateCase(store,c.id,{evidence:{revision,method:'source',verdict:'confirmed',summary:'trace',limitations:[]}}),/attestation/);
 await assert.rejects(()=>validateCase(store,c.id,{attest:true,actor:'analyst',evidence:{revision:'e'.repeat(40),method:'runtime',verdict:'confirmed',summary:'trace',limitations:[]}}),/bind revision/);
});
test('source context refuses a symlink escape and a dirty source snapshot',async()=>{
 const root=await mkdtemp(path.join(os.tmpdir(),'openfix-path-')),repo=path.join(root,'repo');await fixtureRepo(repo);
 const {store,c}=imported();c.revision=await (await import('../src/workflow/util.mjs')).git(repo,['rev-parse','HEAD']);
 await writeFile(path.join(repo,'src/invoices.mjs'),'dirty');await assert.rejects(()=>enrichCase(store,c.id,{repo}),/clean/);
 const outside=path.join(root,'outside.mjs');await writeFile(outside,'outside');await symlink(outside,path.join(repo,'escape.mjs'));
 const {containedFile}=await import('../src/workflow/util.mjs');await assert.rejects(()=>containedFile(repo,'escape.mjs'),/escapes/);
});
test('corrupt state fails explicitly and leaves original bytes intact',async()=>{
 const dir=await mkdtemp(path.join(os.tmpdir(),'openfix-corrupt-')),file=path.join(dir,'cases.json');await writeFile(file,'{broken');await assert.rejects(()=>loadStore(dir),/Cannot read/);assert.equal(await readFile(file,'utf8'),'{broken');
});
test('audit checkpoint detects direct state changes',async()=>{
 const dir=await mkdtemp(path.join(os.tmpdir(),'openfix-audit-'));await mutateStore(dir,s=>event(s,'test',{}));const file=path.join(dir,'cases.json'),state=JSON.parse(await readFile(file,'utf8'));state.cases.fake={id:'fake'};await writeFile(file,JSON.stringify(state));await assert.rejects(()=>loadStore(dir),/audit checkpoint/);
});
test('nonempty state cannot bypass integrity checks by deleting its audit',async()=>{
 const dir=await mkdtemp(path.join(os.tmpdir(),'openfix-noaudit-'));await writeFile(path.join(dir,'cases.json'),JSON.stringify({schemaVersion:3,revision:1,cases:{fake:{}},artifacts:{},audit:[]}));await assert.rejects(()=>loadStore(dir),/audit checkpoint/);
});
test('concurrent writers fail busy instead of silently overwriting state',async()=>{
 const dir=await mkdtemp(path.join(os.tmpdir(),'openfix-lock-'));let release,started;const ready=new Promise(resolve=>started=resolve),gate=new Promise(resolve=>release=resolve);
 const first=mutateStore(dir,async s=>{started();await gate;event(s,'first',{});});await ready;await assert.rejects(()=>mutateStore(dir,s=>event(s,'second',{})),/busy/);release();await first;assert.equal((await loadStore(dir)).revision,1);
});
test('HTML safely embeds malicious finding text without executable markup',()=>{
 const doc=baseDoc();doc.findings[0].title='</script><script>window.pwned=true</script>';const {store}=imported(doc);const html=renderReport(store);assert.ok(!html.includes('<script>window.pwned'));assert.ok(html.includes('\\u003c/script\\u003e'));assert.ok(html.includes('textContent'));
});
test('the actual CLI persists imported cases across separate invocations',async()=>{
 const root=await mkdtemp(path.join(os.tmpdir(),'openfix-cli-')),input=path.join(root,'findings.json'),dir=path.join(root,'store'),report=path.join(root,'report.html');await writeFile(input,JSON.stringify(baseDoc()));
 const cli=fileURLToPath(new URL('../src/openfix.mjs',import.meta.url));await exec(process.execPath,[cli,'import',input,'--store',dir]);assert.equal(Object.keys((await loadStore(dir)).cases).length,1);
 await exec(process.execPath,[cli,'report','--store',dir,'--out',report]);assert.match(await readFile(report,'utf8'),/Tenant boundary/);
});
test('integrated demo executes vulnerable, inconclusive, false-positive and bad-fix branches',async()=>{
 const result=await runDemo();assert.deepEqual(result.metrics,{cases:4,observations:5,confirmed:1,disproved:1,attemptedRuns:5,incompleteRuns:1,verifiedPatches:1,conflicts:1});assert.equal(result.brokenPatch,'failed');assert.equal(result.correctedPatch,'passed');
 const store=await loadStore(result.store),c=store.cases[result.correlatedCase];assert.equal(c.runs.filter(r=>r.purpose==='patch-verification').length,2);assert.equal(c.lifecycle.review.decision,'approved');assert.equal(c.lifecycle.rollout,undefined);
 assert.throws(()=>reviewCase(store,c.id,{actor:c.lifecycle.patch.author.id,patchHash:c.lifecycle.patch.sha256,reason:'self approval'}),/own patch/);
 assert.throws(()=>reviewCase(store,c.id,{actor:'another-reviewer',patchHash:'d'.repeat(64),reason:'stale patch'}),/exact patch/);
 assert.throws(()=>closeCase(store,c.id,{actor:'reviewer',reason:'premature',evidence:{revision:c.lifecycle.patch.headCommit,status:'passed',summary:'claimed deployed'}}),/rollout/);
 const ctx=context('new-owner');ctx.assets[0].repository=c.repository;ctx.assets[0].revision=c.revision;ctx.assets[0].assetId=c.assetId;ctx.assets[0].deployedRevision=c.revision;
 await enrichCase(store,c.id,{manifest:ctx,manifestArtifact:{file:'/tmp/new-context.json',digest:digest(ctx)}});assert.equal(assessCase(c).status,'needs_reacceptance');assert.equal(assessCase(c).remediationAllowed,false);assert.throws(()=>reviewCase(store,c.id,{actor:'reviewer',patchHash:c.lifecycle.patch.sha256,reason:'changed context'}),/Context changed/);
});
