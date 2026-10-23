import { createHash } from 'node:crypto';
import { readFile, realpath } from 'node:fs/promises';
import path from 'node:path';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';

export const exec = promisify(execFile);
export const invariant = (ok, message) => { if (!ok) throw new Error(message); };
export const sha256 = value => createHash('sha256').update(value).digest('hex');
export const stable = value => JSON.stringify(sort(value));
function sort(value) {
  if (Array.isArray(value)) return value.map(sort);
  if (value && typeof value === 'object') return Object.fromEntries(Object.keys(value).sort().filter(k => value[k] !== undefined).map(k => [k, sort(value[k])]));
  return value;
}
export const digest = value => sha256(stable(value));
export const immutableRevision = value => typeof value === 'string' && /^[a-f\d]{40,64}$/i.test(value);
export const now = () => new Date().toISOString();

export function redact(value, depth = 0) {
  invariant(depth < 40, 'Input nesting is too deep');
  if (Array.isArray(value)) return value.map(v => redact(v, depth + 1));
  if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).map(([k,v]) => [k, /^(password|secret|access_token|api_key|authorization|private_key)$/i.test(k) ? '[REDACTED]' : redact(v, depth + 1)]));
  if (typeof value !== 'string') return value;
  return value.replace(/-----BEGIN [^-]*PRIVATE KEY-----[\s\S]*?-----END [^-]*PRIVATE KEY-----/g, '[REDACTED PRIVATE KEY]')
    .replace(/\b(?:sk-(?:proj-)?[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16})\b/g, '[REDACTED CREDENTIAL]');
}
export async function jsonFile(file) {
  const data = await readFile(file);
  invariant(data.length <= 20 * 1024 * 1024, 'Input exceeds 20 MiB');
  let value;
  try { value=JSON.parse(data.toString('utf8')); } catch { throw new Error(`Invalid JSON in ${path.basename(file)}; input contents were not logged`); }
  return { value, digest: sha256(data), file: path.resolve(file) };
}
export async function containedFile(root, relative) {
  invariant(typeof relative === 'string' && relative && !path.isAbsolute(relative) && !relative.includes('\\') && !relative.split('/').includes('..'), 'Source path must be repository-relative');
  const base = await realpath(root), file = await realpath(path.join(base, relative));
  invariant(file.startsWith(base + path.sep), 'Source path escapes repository (including symlink)');
  return file;
}
export async function git(repo, args) {
  const result = await exec('git', ['-C', path.resolve(repo), ...args], { timeout: 15_000, maxBuffer: 8 * 1024 * 1024, env: { PATH: process.env.PATH, GIT_TERMINAL_PROMPT: '0', GIT_CONFIG_NOSYSTEM: '1' } });
  return result.stdout.trim();
}
export async function repositorySnapshot(repo, expected) {
  invariant(immutableRevision(expected), 'An immutable finding revision is required');
  const head = await git(repo, ['rev-parse', 'HEAD']);
  invariant(head === expected, `Repository HEAD ${head} does not match evidence revision ${expected}`);
  invariant(!(await git(repo, ['status', '--porcelain', '--untracked-files=all'])), 'Repository must be clean; commit or remove changes before recording evidence');
  return head;
}
