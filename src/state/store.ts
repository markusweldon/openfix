/**
 * Local state under .openfix/ (gitignored).
 *
 * Stores:
 *   findings[]      — last ingest
 *   remediations[]  — agent ids, PR urls, fingerprints already handled
 *
 * inFlightFingerprints() feeds policy so we don't spawn two agents for one issue.
 */
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { FindingSchema, type Finding } from "../types/finding.js";
import { z } from "zod";

const STATE_DIR = ".openfix";

const RemediationRecordSchema = z.object({
  findingId: z.string(),
  fingerprint: z.string(),
  agentId: z.string(),
  runId: z.string().optional(),
  status: z.enum(["started", "finished", "error", "cancelled"]),
  prUrl: z.string().optional(),
  startedAt: z.string(),
  finishedAt: z.string().optional(),
  error: z.string().optional(),
});

export type RemediationRecord = z.infer<typeof RemediationRecordSchema>;

const StateSchema = z.object({
  findings: z.array(FindingSchema).default([]),
  remediations: z.array(RemediationRecordSchema).default([]),
  /** Most recent cloud agent — used by `status --last` / `resume --last`. */
  lastAgentId: z.string().optional(),
  lastPrUrl: z.string().optional(),
  lastRunId: z.string().optional(),
});

export type OpenFixState = z.infer<typeof StateSchema>;

/** Serialize state writes so concurrent remediations don't clobber each other. */
let stateWriteChain: Promise<unknown> = Promise.resolve();

function withStateLock<T>(fn: () => Promise<T>): Promise<T> {
  const run = stateWriteChain.then(fn, fn);
  stateWriteChain = run.then(
    () => undefined,
    () => undefined,
  );
  return run;
}

function statePath(cwd = process.cwd()): string {
  return path.join(cwd, STATE_DIR, "state.json");
}

export async function ensureStateDir(cwd = process.cwd()): Promise<string> {
  const dir = path.join(cwd, STATE_DIR);
  await mkdir(dir, { recursive: true });
  return dir;
}

export async function loadState(cwd = process.cwd()): Promise<OpenFixState> {
  try {
    const text = await readFile(statePath(cwd), "utf8");
    return StateSchema.parse(JSON.parse(text));
  } catch {
    return { findings: [], remediations: [] };
  }
}

export async function saveState(
  state: OpenFixState,
  cwd = process.cwd(),
): Promise<void> {
  await ensureStateDir(cwd);
  await writeFile(statePath(cwd), JSON.stringify(state, null, 2) + "\n", "utf8");
}

/** Replace the ingested finding set (full refresh per ingest). */
export async function saveFindings(
  findings: Finding[],
  cwd = process.cwd(),
): Promise<void> {
  const state = await loadState(cwd);
  state.findings = findings;
  await saveState(state, cwd);
}

/** Insert or update a remediation row keyed by agentId. */
export async function upsertRemediation(
  record: RemediationRecord,
  cwd = process.cwd(),
): Promise<void> {
  await withStateLock(async () => {
    const state = await loadState(cwd);
    const idx = state.remediations.findIndex(
      (r) => r.agentId === record.agentId,
    );
    if (idx >= 0) state.remediations[idx] = record;
    else state.remediations.push(record);
    // Track latest agent for demo `--last` (even mid-run / on error).
    if (record.agentId && record.agentId !== "unknown") {
      state.lastAgentId = record.agentId;
      if (record.runId) state.lastRunId = record.runId;
      if (record.prUrl) state.lastPrUrl = record.prUrl;
    }
    await saveState(state, cwd);
  });
}

/** Resolve bc-… for `status --last` / `resume --last`. */
export async function getLastAgentId(cwd = process.cwd()): Promise<string> {
  const state = await loadState(cwd);
  if (!state.lastAgentId) {
    throw new Error(
      "No lastAgentId in .openfix/state.json. Run openfix remediate first, or pass bc-… explicitly.",
    );
  }
  return state.lastAgentId;
}

export async function getLastPrUrl(cwd = process.cwd()): Promise<string | undefined> {
  const state = await loadState(cwd);
  return state.lastPrUrl;
}

/** Fingerprints already started or finished → policy marks them suppress_noise. */
export function inFlightFingerprints(state: OpenFixState): Set<string> {
  return new Set(
    state.remediations
      .filter((r) => r.status === "started" || r.status === "finished")
      .map((r) => r.fingerprint),
  );
}
