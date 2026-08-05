/**
 * Cursor SDK remediator — the actual agent integration.
 *
 * Interview talking point:
 *   Agent.create({ cloud, autoCreatePR }) → send(prompt) → stream() → wait()
 *   Later: Agent.get / Agent.resume for async multi-step.
 *
 * Distinguishes:
 *   CursorAgentError  → never started (auth/config) → exit-style failure
 *   result.status error → started but failed mid-run
 */
import { Agent, CursorAgentError } from "@cursor/sdk";
import type { Finding } from "../types/finding.js";
import { requireCloudConfig } from "../config.js";
import {
  upsertRemediation,
  type RemediationRecord,
} from "../state/store.js";
import { buildRemediationPrompt, buildResumePrompt } from "./prompt.js";
import {
  createLabeledStreamWriter,
  printNextSteps,
} from "../cli/helpers.js";

/** Pull request URL from a finished cloud run, if the SDK attached one. */
function prUrlFromResult(result: {
  git?: { branches?: Array<{ prUrl?: string }> };
}): string | undefined {
  return result.git?.branches?.[0]?.prUrl;
}

export interface RemediateOptions {
  /** Label for multiplexed streams when running concurrent agents (e.g. A1). */
  streamLabel?: string;
  /** Fleet mode prints one summary; skip per-agent next-steps. */
  suppressNextSteps?: boolean;
}

/**
 * Spawn one cloud agent for one auto_fix finding.
 * `await using` disposes the agent handle when the function ends (no resource leak).
 */
export async function remediateFinding(
  finding: Finding,
  options: RemediateOptions = {},
): Promise<RemediationRecord> {
  const cfg = requireCloudConfig();
  const prompt = buildRemediationPrompt(finding);
  const label = options.streamLabel;
  const log = (msg: string) => {
    if (label) console.log(`[${label}] ${msg}`);
    else console.log(msg);
  };

  let agentId = "";
  let runId = "";

  try {
    // Cloud runtime: Cursor VM clones OPENFIX_TARGET_REPO and can open a PR.
    await using agent = await Agent.create({
      apiKey: cfg.apiKey,
      model: { id: cfg.model },
      cloud: {
        repos: [{ url: cfg.targetRepo, startingRef: cfg.startingRef }],
        autoCreatePR: true, // artifact = PR for humans, never silent merge
        skipReviewerRequest: true, // quieter for demo / CI-style automation
      },
    });

    agentId = agent.agentId; // bc-… — save this for status/resume
    const run = await agent.send(prompt);
    runId = run.id;

    // Persist early so triage can suppress duplicate fingerprints if we crash mid-run.
    const started: RemediationRecord = {
      findingId: finding.id,
      fingerprint: finding.fingerprint,
      agentId,
      runId,
      status: "started",
      startedAt: new Date().toISOString(),
    };
    await upsertRemediation(started);
    log(`Started agent=${agentId} run=${runId} finding=${finding.id}`);

    // Live demo: stream assistant text (line-prefixed when concurrent).
    const streamOut = label
      ? createLabeledStreamWriter(label)
      : {
          write: (t: string) => process.stdout.write(t),
          flush: () => undefined,
        };

    for await (const event of run.stream()) {
      if (event.type === "assistant") {
        for (const block of event.message.content) {
          if (block.type === "text" && block.text) {
            streamOut.write(block.text);
          }
        }
      }
    }
    streamOut.flush();

    // Always wait() — confirms finished/error/cancelled and yields git/PR metadata.
    const result = await run.wait();
    const finished: RemediationRecord = {
      ...started,
      status:
        result.status === "error"
          ? "error"
          : result.status === "finished"
            ? "finished"
            : "cancelled",
      prUrl: prUrlFromResult(result),
      finishedAt: new Date().toISOString(),
      error: result.status === "error" ? `run failed: ${result.id}` : undefined,
    };
    await upsertRemediation(finished);

    if (finished.prUrl) log(`PR: ${finished.prUrl}`);
    log(`Status: ${finished.status} agent=${agentId} run=${runId}`);
    if (!options.suppressNextSteps) {
      printNextSteps(agentId, finished.prUrl);
    }
    return finished;
  } catch (err) {
    // Startup/config failures (bad key, bad repo) — different from mid-run errors.
    if (err instanceof CursorAgentError) {
      const failed: RemediationRecord = {
        findingId: finding.id,
        fingerprint: finding.fingerprint,
        agentId: agentId || "unknown",
        runId: runId || undefined,
        status: "error",
        startedAt: new Date().toISOString(),
        finishedAt: new Date().toISOString(),
        error: `startup failed: ${err.message} (retryable=${err.isRetryable})`,
      };
      await upsertRemediation(failed);
      throw err;
    }
    throw err;
  }
}

/** Async check-in: inspect a durable cloud agent by id (bc-…). */
export async function statusAgent(agentId: string): Promise<void> {
  const cfg = requireCloudConfig();
  const info = await Agent.get(agentId, { apiKey: cfg.apiKey });
  console.log(JSON.stringify(info, null, 2));
}

/**
 * Multi-step follow-up: same agent, new prompt (e.g. address PR review comments).
 * Proves durable conversation — not a one-shot script.
 */
export async function resumeAgent(
  agentId: string,
  prompt: string,
): Promise<void> {
  const cfg = requireCloudConfig();
  await using agent = await Agent.resume(agentId, {
    apiKey: cfg.apiKey,
  });

  const run = await agent.send(buildResumePrompt(prompt));
  console.log(`Resumed agent=${agent.agentId} run=${run.id}`);

  for await (const event of run.stream()) {
    if (event.type === "assistant") {
      for (const block of event.message.content) {
        if (block.type === "text" && block.text) {
          process.stdout.write(block.text);
        }
      }
    }
  }

  const result = await run.wait();
  const prUrl = prUrlFromResult(result);
  console.log(`\nResume status: ${result.status}`);
  if (prUrl) console.log(`PR: ${prUrl}`);
}
