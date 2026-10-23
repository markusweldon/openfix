import { fileURLToPath } from 'node:url';
import path from 'node:path';
import os from 'node:os';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { exec, repositorySnapshot, containedFile, redact, digest, now } from './util.mjs';

export async function runValidationProfile({ repo, revision, profile, execute, subject }) {
  let job;
  const result = { id: `run-${Date.now()}-${Math.random().toString(16).slice(2,8)}`, profile, revision, startedAt:now(),
    subject, isolation:'bounded-local-process', limits:['Local reference runner; not a container or network-isolation boundary. Use an isolated worker for untrusted customer code.','Checks cover only the reference invoice lookup and its legitimate-access behavior.'], checks:[] };
  try {
    if (!execute) throw new Error('Execution was not authorized: add --execute for the trusted local reference profile, or import reviewed external evidence');
    if (profile !== 'tenant-isolation') throw new Error(`No installed validator for profile ${profile}. Finding remains inconclusive.`);
    if (subject?.category !== 'sast' || subject?.file !== 'src/invoices.mjs' || subject?.line !== 3 || subject?.cwe !== 'CWE-639') throw new Error('The tenant-isolation profile covers only the CWE-639 invoice lookup at src/invoices.mjs:3; this case is outside its evidence scope');
    if (!repo) throw new Error('Validation needs --repo at the immutable finding revision');
    await repositorySnapshot(repo,revision);
    await containedFile(repo,'src/invoices.mjs');
    const probe = fileURLToPath(new URL('./tenant-probe.mjs',import.meta.url));
    job=await mkdtemp(path.join(os.tmpdir(),'openfix-check-'));
    const output=path.join(job,'result.json');
    const childEnv={...process.env};
    for(const key of ['OPENAI_API_KEY','CURSOR_API_KEY','GH_TOKEN','GITHUB_TOKEN','AWS_ACCESS_KEY_ID','AWS_SECRET_ACCESS_KEY','AWS_SESSION_TOKEN'])delete childEnv[key];
    const { stdout, stderr } = await exec(process.execPath,[probe,path.resolve(repo),output],{ timeout:10_000, maxBuffer:64*1024,
      env:childEnv, windowsHide:true });
    await repositorySnapshot(repo,revision);
    const observed = JSON.parse(await readFile(output,'utf8'));
    if (![observed.legitimate,observed.leaked,observed.blocked].every(x => typeof x === 'boolean')) throw new Error('Malformed validator result');
    result.observed = observed; result.stdout = redact(stdout); result.stderr = redact(stderr);
    result.checks = [{ name:'security', status: observed.blocked ? 'passed' : 'failed', detail:observed.leaked ? 'A tenant received another tenant invoice' : observed.blocked ? 'Cross-tenant request was denied' : 'Unexpected cross-tenant behavior' },
      { name:'regression', status:observed.legitimate ? 'passed' : 'failed', detail:observed.legitimate ? 'The owning tenant retained access to its invoice' : 'Legitimate invoice access failed' }];
    result.status = 'completed';
  } catch (error) {
    result.status = 'incomplete'; result.error = redact(error.message);
    result.checks = [{ name:'security',status:'not_run' },{ name:'regression',status:'not_run' }];
  }
  if(job)await rm(job,{recursive:true,force:true});
  result.finishedAt = now(); result.sha256 = digest(result); return result;
}
export function validationVerdict(run) {
  if (run.status !== 'completed' || !run.observed?.legitimate) return 'inconclusive';
  if (run.observed.leaked) return 'confirmed';
  if (run.observed.blocked) return 'disproved';
  return 'inconclusive';
}
export function verificationVerdict(run) {
  if (run.status !== 'completed') return 'incomplete';
  return run.checks.every(c => c.status === 'passed') ? 'passed' : 'failed';
}
