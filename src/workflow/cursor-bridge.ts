/** Optional executor bridge: only invoked by an accepted v0.2 case dispatch. */
import { readFile, writeFile } from 'node:fs/promises';
import { FindingSchema } from '../types/finding.js';
import { saveFindings } from '../state/store.js';
import { remediateFinding } from '../remediator/agent.js';

const job=JSON.parse(await readFile(process.argv[2]!, 'utf8'));
const finding=FindingSchema.parse(job.finding);
process.env.OPENFIX_TARGET_REPO=job.run.repoUrl;
process.env.OPENFIX_COMMIT_SHA=job.run.commitSha;
await saveFindings([finding],job.run);
const result=await remediateFinding(finding,{quiet:true,suppressNextSteps:true});
await writeFile(process.argv[3]!,JSON.stringify(result),{flag:'wx',mode:0o600});
if(result.status!=='finished'||!result.prUrl)process.exitCode=1;
