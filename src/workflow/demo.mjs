import { mkdtemp, mkdir, writeFile, access } from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import { exec, jsonFile, invariant, now } from './util.mjs';
import { mutateStore, loadStore, event } from './store.mjs';
import { normalizeDocument, importObservations } from './import.mjs';
import { enrichCase, assessCase } from './enrich.mjs';
import { validateCase, decideCase, recordCasePatch, verifyCasePatch, reviewCase } from './operations.mjs';
import { renderReport, reportData } from './report.mjs';

export const VULNERABLE=`export function lookupInvoice(user, id, invoices) {
  if (!user?.tenantId) throw new Error('unauthorized');
  return invoices.find(invoice => invoice.id === id) || null;
}
`;
export const SECURE=`export function lookupInvoice(user, id, invoices) {
  if (!user?.tenantId) throw new Error('unauthorized');
  return invoices.find(invoice => invoice.id === id && invoice.tenantId === user.tenantId) || null;
}
`;
export const BROKEN=`export function lookupInvoice(user, id, invoices) {
  if (!user?.tenantId) throw new Error('unauthorized');
  return null;
}
`;
export async function fixtureRepo(directory,content=VULNERABLE) {
  await mkdir(path.join(directory,'src'),{recursive:true});
  await writeFile(path.join(directory,'src/invoices.mjs'),content);
  await writeFile(path.join(directory,'package.json'),JSON.stringify({name:'billing-demo',version:'1.0.0',type:'module'}));
  const run=args=>exec('git',['-C',directory,...args],{env:{PATH:process.env.PATH,GIT_AUTHOR_NAME:'OpenFix Demo',GIT_AUTHOR_EMAIL:'demo@example.invalid',GIT_COMMITTER_NAME:'OpenFix Demo',GIT_COMMITTER_EMAIL:'demo@example.invalid',GIT_AUTHOR_DATE:'2026-10-23T00:00:00Z',GIT_COMMITTER_DATE:'2026-10-23T00:00:00Z',GIT_CONFIG_NOSYSTEM:'1'}});
  await run(['init','-q']);await run(['add','.']);await run(['commit','-qm','Reference application']);return (await run(['rev-parse','HEAD'])).stdout.trim();
}
export async function commitFixture(directory,content,message) {
  await writeFile(path.join(directory,'src/invoices.mjs'),content);
  await exec('git',['-C',directory,'add','src/invoices.mjs']);
  await exec('git',['-C',directory,'-c','user.name=OpenFix Demo','-c','user.email=demo@example.invalid','commit','-qm',message],{env:{PATH:process.env.PATH,GIT_AUTHOR_DATE:'2026-10-23T00:01:00Z',GIT_COMMITTER_DATE:'2026-10-23T00:01:00Z'}});
  return (await exec('git',['-C',directory,'rev-parse','HEAD'])).stdout.trim();
}
export async function runDemo({directory,out}={}) {
  let root;
  if(directory){root=path.resolve(directory);try{await access(root);throw new Error('Demo directory must be new; existing files are preserved');}catch(error){if(error.code!=='ENOENT')throw error;}await mkdir(root,{recursive:true});}
  else root=await mkdtemp(path.join(os.tmpdir(),'openfix-customer-'));
  const repo=path.join(root,'billing-app'),secureRepo=path.join(root,'already-secure-app'),storeDir=path.join(root,'workflow'),inputDir=path.join(root,'inputs');
  await mkdir(inputDir);const revision=await fixtureRepo(repo),secureRevision=await fixtureRepo(secureRepo,SECURE),observedAt=now();
  const repository='https://example.invalid/customer/billing',secureUrl='https://example.invalid/customer/secure-billing',assetId='service:billing-api';
  const sarif={version:'2.1.0',runs:[{tool:{driver:{name:'Semgrep (synthetic fixture)',rules:[{id:'tenant-ownership',properties:{tags:['CWE-639'],'security-severity':'8.1'}}]}},versionControlProvenance:[{repositoryUri:repository,revisionId:revision}],results:[{ruleId:'tenant-ownership',message:{text:'Invoice lookup may cross a tenant boundary'},locations:[{physicalLocation:{artifactLocation:{uri:'src/invoices.mjs'},region:{startLine:3}}}],properties:{enrichment:{reachability:true,observedAt},observedAt}}]}]};
  const alerts={repository,assetId,alerts:[{number:7,rule:{id:'tenant-check',description:'Cross-tenant invoice access',security_severity_level:'high',tags:['CWE-639']},tool:{name:'GitHub code scanning (synthetic fixture)'},most_recent_instance:{commit_sha:revision,location:{path:'src/invoices.mjs',start_line:3}},enrichment:{reachability:true,observedAt}}]};
  const snyk={repository,revision,assetId,targetFile:'package.json',vulnerabilities:[{id:'DEMO-ADVISORY-001',packageName:'example-dependency',version:'1.0.0',severity:'medium',title:'Hypothetical dependency issue; no validator installed',identifiers:{CWE:['CWE-400']},enrichment:{reachability:false,observedAt}}]};
  const cloud={schemaVersion:2,producer:'Cloud context export (synthetic fixture)',repository,revision,assetId,observedAt,findings:[{id:'cloud-exposure-1',title:'Conflicting service-owner mapping',ruleId:'exposure-review',severity:'high',category:'cloud',enrichment:{owner:'platform-team',exposure:'internet',observedAt}}]};
  const falsePositive={schemaVersion:2,producer:'Code review report (synthetic fixture)',repository:secureUrl,revision:secureRevision,assetId:'service:secure-billing',observedAt,findings:[{id:'already-protected',title:'Suspected tenant bypass on an already protected lookup',ruleId:'tenant-ownership',cwe:'CWE-639',file:'src/invoices.mjs',line:3,severity:'high'}]};
  const context={schemaVersion:1,assets:[{assetId,repository,revision,owner:'billing-team',exposure:'internet',criticality:'critical',deployedRevision:revision,observedAt},{assetId:'service:secure-billing',repository:secureUrl,revision:secureRevision,owner:'billing-team',exposure:'internal',criticality:'standard',deployedRevision:secureRevision,observedAt}]};
  const brief={problem:'Reduce investigation and reviewer effort without accepting false fixes',stakeholders:['AppSec','billing owner','platform'],scope:'Two fixture services; one code issue and contextual counterexamples',constraints:['No automatic merge or deployment','No customer credentials in jobs'],baseline:'Not measured; no ROI claim',pilotDecision:'Expand only after accepted fixes and negative-case review'};
  const documents=[['semgrep.sarif',sarif],['github-alerts.json',alerts],['snyk.json',snyk],['cloud.json',cloud],['false-positive.json',falsePositive]];
  for(const [name,value] of documents){const file=path.join(inputDir,name);await writeFile(file,JSON.stringify(value,null,2));const artifact=await jsonFile(file);const n=normalizeDocument(value,{assetId},artifact);await mutateStore(storeDir,s=>importObservations(s,n,artifact,brief));}
  const contextPath=path.join(inputDir,'asset-context.json');await writeFile(contextPath,JSON.stringify(context,null,2));const ctx=await jsonFile(contextPath);
  let store=await loadStore(storeDir);const cases=Object.values(store.cases),target=cases.find(c=>c.repository===repository&&c.category==='sast'),dependency=cases.find(c=>c.category==='sca'),disproved=cases.find(c=>c.repository===secureUrl),conflict=cases.find(c=>c.category==='cloud');
  invariant(target.observations.length===2,'Demo must correlate the two code observations');
  for(const c of cases)await mutateStore(storeDir,s=>enrichCase(s,c.id,{manifest:ctx.value,manifestArtifact:ctx,repo:c.category==='sast'?(c.id===target.id?repo:secureRepo):undefined}));
  const reused=await mutateStore(storeDir,s=>enrichCase(s,target.id,{manifest:ctx.value,manifestArtifact:ctx,repo}));
  await mutateStore(storeDir,s=>validateCase(s,target.id,{repo,profile:'tenant-isolation',execute:true}));
  await mutateStore(storeDir,s=>validateCase(s,dependency.id,{repo,profile:'dependency-runtime',execute:true}));
  await mutateStore(storeDir,s=>validateCase(s,disproved.id,{repo:secureRepo,profile:'tenant-isolation',execute:true}));
  await mutateStore(storeDir,s=>decideCase(s,disproved.id,{actor:'appsec-reviewer',decision:'dismissed',reason:'Recorded probe denies cross-tenant access and preserves legitimate behavior'}));
  await mutateStore(storeDir,s=>decideCase(s,target.id,{actor:'appsec-reviewer',decision:'accepted',owner:'billing-team',priority:'P1',reason:'Reproduced tenant boundary failure on an exposed billing service; bounded change only'}));
  const badHead=await commitFixture(repo,BROKEN,'Incorrect patch blocks all invoice access');
  await mutateStore(storeDir,s=>recordCasePatch(s,target.id,{repo,head:badHead,actor:'reference-patch-author',engine:'reference-code-edit',summary:'Deliberately incorrect patch for negative-case verification'}));
  const bad=await mutateStore(storeDir,s=>verifyCasePatch(s,target.id,{repo,profile:'tenant-isolation',execute:true,actor:'independent-verifier'}));
  invariant(bad.status==='failed','A deny-all patch must fail legitimate behavior');
  try{await mutateStore(storeDir,s=>reviewCase(s,target.id,{actor:'appsec-reviewer',patchHash:s.cases[target.id].lifecycle.patch.sha256,reason:'Attempted approval of a broken patch'}));throw new Error('Broken patch was approved');}
  catch(error){invariant(/Passing independent verification/.test(error.message),'Unexpected review failure');await mutateStore(storeDir,s=>event(s,'operation_denied',{id:target.id,command:'review',reason:error.message},'appsec-reviewer'));}
  const goodHead=await commitFixture(repo,SECURE,'Constrain invoice lookup to the authenticated tenant');
  await mutateStore(storeDir,s=>recordCasePatch(s,target.id,{repo,head:goodHead,actor:'reference-patch-author',engine:'reference-code-edit',summary:'Tenant predicate preserves the owning tenant lookup'}));
  const good=await mutateStore(storeDir,s=>verifyCasePatch(s,target.id,{repo,profile:'tenant-isolation',execute:true,actor:'independent-verifier'}));
  invariant(good.status==='passed','Correct patch must pass security and legitimate behavior');
  await mutateStore(storeDir,s=>reviewCase(s,target.id,{actor:'appsec-reviewer',patchHash:s.cases[target.id].lifecycle.patch.sha256,reason:'Exact artifact passes recorded security and legitimate-behavior checks; deployment remains separate'}));
  store=await loadStore(storeDir);invariant(assessCase(store.cases[conflict.id]).context.owner.status==='conflicting','Conflicting owner context must remain visible');
  const report=path.resolve(out||path.join(root,'workbench.html'));await mkdir(path.dirname(report),{recursive:true});await writeFile(report,renderReport(store,{demo:true}));
  await writeFile(path.join(root,'casebook.json'),JSON.stringify(reportData(store),null,2)+'\n');
  return {demo:'Integrated workflow; synthetic imported reports, executed local checks, reference code edits, no model call or deployment',directory:root,store:storeDir,report,
    metrics:reportData(store).metrics,correlatedCase:target.id,reusedEvidence:reused.reused,brokenPatch:bad.status,correctedPatch:good.status,
    outcomes:Object.values(store.cases).map(c=>({id:c.id,status:assessCase(c).status,title:c.title}))};
}
