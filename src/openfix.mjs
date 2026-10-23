#!/usr/bin/env node
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { writeFile, mkdir } from 'node:fs/promises';
import { spawn } from 'node:child_process';
import { jsonFile, invariant } from './workflow/util.mjs';
import { loadStore, mutateStore, event } from './workflow/store.mjs';
import { normalizeDocument, importObservations } from './workflow/import.mjs';
import { assessCase, enrichCase } from './workflow/enrich.mjs';
import { getCase, validateCase, decideCase, recordCasePatch, verifyCasePatch, reviewCase, rolloutCase, closeCase, taskPacket, writeTaskPacket } from './workflow/operations.mjs';
import { reportData, renderReport, serveReport } from './workflow/report.mjs';
import { providers,dispatchCursor } from './workflow/providers.mjs';

const HELP=`OpenFix 0.2 — findings intelligence and controlled remediation

  import <files…>   Import SARIF, GitHub alerts, Snyk JSON or findings envelopes
  enrich <id|all>   --context assets.json [--repo /path/to/repository]
  list             Show case state, priority and next decision
  show <id>        Inspect a case and its evidence plan
  validate <id>    --repo <path> --profile tenant-isolation --execute
                   Or --evidence <file> --attest --actor <operator>
  decide <id>      --decision accepted|deferred|dismissed --actor <name>
                   --owner <team> --reason <text> [--priority P1]
  plan <id>        Export bounded, agent-ready context [--out <new-directory>]
  providers        Show source and execution adapter capabilities
  dispatch <id>    --engine cursor --execute --publish-draft --actor <operator>
                   Optional live executor; publishes a draft pull request
  patch <id>       Record an actual git diff: --repo <path> --head <commit> --actor <author>
  verify <id>      --repo <path> --profile tenant-isolation --execute --actor <verifier>
  review <id>      --patch-hash <sha256> --actor <reviewer> --reason <text>
                   [--decision approved|changes_requested]
  rollout <id>     Attest an external rollout: --deployed-revision <sha> --change-record <ref> --actor <name>
  close <id>       --evidence <post-change.json> --actor <name> --reason <text>
  report           --out <report.html> [--demo-label]
  serve            Read-only local workbench [--port 4317]
  demo             Run the integrated fixture workflow [--dir <new-directory>] [--out report.html]
  legacy <args…>   Original Cursor CLI (requires installed legacy dependencies)

Shared options: --store <directory> (default .openfix/workflow), --json
Import scope: --repository <url> --revision <immutable-sha> --asset-id <id> [--brief brief.json]
Local actor labels are audit assertions, not authenticated enterprise identities.
Draft publication requires --publish-draft. No command merges or deploys a change.
`;
function argumentsOf(argv) {
  const flags={},args=[],bool=new Set(['json','execute','publish-draft','attest','demo-label','help']);
  const known=new Set(['store','repository','revision','asset-id','brief','context','repo','profile','evidence','actor','decision','owner','reason','priority','out','head','summary','engine','patch-hash','deployed-revision','change-record','port','dir',...bool]);
  for(let i=0;i<argv.length;i++) {
    const value=argv[i];
    if(!value.startsWith('--')) {args.push(value);continue;}
    const key=value.slice(2);invariant(known.has(key),`Unknown option --${key}`);
    if(bool.has(key))flags[key]=true;
    else {invariant(argv[i+1]&&!argv[i+1].startsWith('--'),`--${key} requires a value`);flags[key]=argv[++i];}
  }
  return {flags,args};
}
async function main() {
  const argv=process.argv.slice(2);
  if(argv.length===1&&['--version','-v'].includes(argv[0])){console.log('0.2.0');return;}
  if(argv[0]==='legacy') {
    const script=fileURLToPath(new URL('./cli.ts',import.meta.url));
    const child=spawn(process.execPath,['--import','tsx',script,...argv.slice(1)],{stdio:'inherit'});
    child.on('error',e=>{console.error(e.message);process.exitCode=1});child.on('exit',code=>{process.exitCode=code??1});return;
  }
  const {flags:o,args}=argumentsOf(argv),[command,id,...files]=args;
  if(!command||o.help||command==='help'){console.log(HELP);return;}
  if(command==='--version'||command==='version'){console.log('0.2.0');return;}
  const directory=path.resolve(o.store||'.openfix/workflow');
  const print=value=>console.log(JSON.stringify(value,null,2));
  const change=async fn=>{
    try{return await mutateStore(directory,fn);}
    catch(error){
      try{await mutateStore(directory,s=>event(s,'operation_denied',{id,command,reason:error.message},o.actor||'local-operator'));}catch{/* Corrupt/busy state must remain untouched. */}
      throw error;
    }
  };
  if(command==='import') {
    const paths=[id,...files].filter(Boolean);invariant(paths.length,'Pass at least one input report');
    const brief=o.brief?(await jsonFile(o.brief)).value:{};const docs=await Promise.all(paths.map(jsonFile));
    const normalized=docs.map(artifact=>({artifact,normalized:normalizeDocument(artifact.value,{repository:o.repository,revision:o.revision,assetId:o['asset-id']},artifact)}));
    print(await change(s=>normalized.map(({artifact,normalized:n})=>importObservations(s,n,artifact,brief))));return;
  }
  if(command==='enrich') {
    const context=o.context?await jsonFile(o.context):null;
    print(await change(async s=>{const ids=id==='all'?Object.keys(s.cases):[id];const out=[];for(const caseId of ids)out.push(await enrichCase(s,caseId,{manifest:context?.value,manifestArtifact:context,repo:o.repo}));return out;}));return;
  }
  if(command==='list') {
    const data=reportData(await loadStore(directory));
    const rows=data.cases.map(c=>({id:c.id,title:c.title,sourceCount:c.observations.length,status:c.assessment.status,priority:c.assessment.priority.label,next:c.assessment.nextAction}));
    if(o.json)print(rows);else {console.log('OPENFIX · findings intelligence\n');for(const c of rows)console.log(`${c.id}  ${c.priority}  ${c.status}\n  ${c.title}\n  ${c.next}\n`);if(!rows.length)console.log('No cases. Use openfix import <report>.');}return;
  }
  if(command==='providers'){print(providers);return;}
  if(command==='show'){const c=getCase(await loadStore(directory),id);print({...c,assessment:assessCase(c)});return;}
  if(command==='plan'){const c=getCase(await loadStore(directory),id);print(o.out?await writeTaskPacket(c,o.out):taskPacket(c));return;}
  if(command==='report'){invariant(o.out,'Report needs --out <file.html>');await mkdir(path.dirname(path.resolve(o.out)),{recursive:true});await writeFile(o.out,renderReport(await loadStore(directory),{demo:Boolean(o['demo-label'])}));print({report:path.resolve(o.out)});return;}
  if(command==='serve'){const port=Number(o.port||4317);invariant(Number.isInteger(port)&&port>=0&&port<=65535,'Invalid port');serveReport(directory,{port});return;}
  if(command==='demo'){const {runDemo}=await import('./workflow/demo.mjs');print(await runDemo({directory:o.dir,out:o.out}));return;}
  const options={...o,execute:Boolean(o.execute),attest:Boolean(o.attest),head:o.head,patchHash:o['patch-hash'],deployedRevision:o['deployed-revision'],changeRecord:o['change-record']};
  if(o.evidence)options.evidence=(await jsonFile(o.evidence)).value;
  let result;
  switch(command){
    case 'validate':result=await change(s=>validateCase(s,id,options));break;
    case 'decide':result=await change(s=>decideCase(s,id,options));break;
    case 'patch':result=await change(s=>recordCasePatch(s,id,options));break;
    case 'verify':result=await change(s=>verifyCasePatch(s,id,options));break;
    case 'review':result=await change(s=>reviewCase(s,id,options));break;
    case 'rollout':result=await change(s=>rolloutCase(s,id,options));break;
    case 'close':result=await change(s=>closeCase(s,id,options));break;
    case 'dispatch':invariant(o.engine==='cursor','Use plan --out for native Codex workflows; only cursor has a live executor bridge here');result=await change(s=>dispatchCursor(s,id,options));break;
    default:throw new Error(`Unknown command ${command}. Use openfix help.`);
  }
  print(result);
  if(result.verdict==='inconclusive'||result.status==='incomplete')process.exitCode=2;
  if(result.status==='failed')process.exitCode=1;
}
main().catch(error=>{console.error(`OpenFix: ${error.message}`);process.exitCode=1;});
