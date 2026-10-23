import { mkdir, readFile, open, rename, rm } from 'node:fs/promises';
import path from 'node:path';
import { randomUUID } from 'node:crypto';
import { digest, invariant, now } from './util.mjs';

export const emptyStore = () => ({ schemaVersion: 3, revision: 0, cases: {}, artifacts: {}, audit: [] });
export function event(store, action, detail, actor = 'local-operator') {
  const previous = store.audit.at(-1)?.hash || null;
  const row = { sequence: store.audit.length + 1, at: now(), actor, action, detail, previous };
  store.audit.push({ ...row, hash: digest(row) });
}
export function checkStore(value) {
  invariant(value?.schemaVersion === 3 && Number.isInteger(value.revision) && value.cases && value.artifacts && Array.isArray(value.audit), 'Invalid workflow store schema; original state preserved');
  let previous = null;
  for (const [i, row] of value.audit.entries()) {
    const { hash, ...body } = row;
    invariant(row.sequence === i + 1 && row.previous === previous && digest(body) === hash, 'Audit chain is corrupt; original state preserved'); previous = hash;
  }
  if (value.audit.length) invariant(value.audit.at(-1).action === 'transaction_committed' && value.audit.at(-1).detail.stateHash === digest({ cases: value.cases, artifacts: value.artifacts }), 'State does not match its audit checkpoint; original state preserved');
  else invariant(value.revision === 0 && Object.keys(value.cases).length === 0 && Object.keys(value.artifacts).length === 0,'Nonempty state is missing its audit checkpoint');
  return value;
}
export async function loadStore(directory) {
  try { return checkStore(JSON.parse(await readFile(path.join(directory, 'cases.json'), 'utf8'))); }
  catch (error) { if (error.code === 'ENOENT') return emptyStore(); throw new Error(`Cannot read workflow state: ${error.message}`, { cause: error }); }
}
export async function mutateStore(directory, operation) {
  await mkdir(directory, { recursive: true, mode: 0o700 });
  const lock = path.join(directory, '.write-lock');
  try { await mkdir(lock); } catch (error) { if (error.code === 'EEXIST') throw new Error('Workflow store is busy; retry after the other writer completes. A stale lock requires operator inspection.'); throw error; }
  let temporary;
  try {
    const store = await loadStore(directory);
    const result = await operation(store);
    store.revision++;
    event(store, 'transaction_committed', { revision: store.revision, stateHash: digest({ cases: store.cases, artifacts: store.artifacts }) });
    checkStore(store);
    temporary = path.join(directory, `.cases-${randomUUID()}.tmp`);
    const handle = await open(temporary, 'wx', 0o600);
    try { await handle.writeFile(JSON.stringify(store, null, 2) + '\n'); await handle.sync(); } finally { await handle.close(); }
    await rename(temporary, path.join(directory, 'cases.json'));
    return result;
  } finally { if (temporary) await rm(temporary, { force: true }); await rm(lock, { recursive: true, force: true }); }
}
