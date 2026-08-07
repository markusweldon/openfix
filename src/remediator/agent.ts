/**
 * Cursor SDK remediator — cloud agent create / stream / wait / resume.
 *
 * Flow: Agent.create({ cloud, autoCreatePR }) → send(prompt) → stream() → wait().
 * Later: Agent.get / Agent.resume for async multi-step follow-ups.
 *
 * Repo / startingRef come from OpenFix run context (ingest) when present:
 * prefer commitSha over branch tip so the agent matches the scanned snapshot.
 * Each remediation row is stamped with openfixRunId (orchestration job ≠ Cursor run id).
 *
 * Distinguishes:
 *   CursorAgentError  → never started (auth/config)
 *   result.status error → started but failed mid-run
 */
import { Agent, CursorAgentError } from "@cursor/sdk";
import type { Finding } from "../types/finding.js";
import { requireCloudConfig } from "../config.js";
import {
  upsertRemediation,
  getCurrentRun,
  type RemediationRecord,
} from "../state/store.js";
import { buildRemediationPrompt, buildResumePrompt } from "./prompt.js";
import {
  createLabeledStreamWriter,
  findingSlug,
  printNextSteps,
  type LanePhase,
} from "../cli/helpers.js";

/** Pull request URL from a finished cloud run, if the SDK attached one. */
function prUrlFromResult(result: {
  git?: { branches?: Array<{ prUrl?: string }> };
}): string | undefined {
  return result.git?.branches?.[0]?.prUrl;
}

export interface RemediateOptions {
  /**
   * Finding-slug label for --verbose streams (e.g. path-traversal).
   * When set with verbose, assistant text is line-prefixed.
   */
  streamLabel?: string;
  /** Print full assistant stream (disables quiet board logging). */
  verbose?: boolean;
  /** Fleet / board mode: skip per-agent next-steps. */
  suppressNextSteps?: boolean;
  /**
   * Quiet board mode: no Started/PR console lines; drive LaneBoard via onPhase.
   * Default when not verbose.
   */
  quiet?: boolean;
  /** Lifecycle updates for the finding-lane board. */
  onPhase?: (
    phase: LanePhase,
    meta?: { detail?: string; prUrl?: string },
  ) => void;
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
  const currentRun = await getCurrentRun();
  const openfixRunId = currentRun?.openfixRunId ?? cfg.openfixRunId;
  const targetRepo = currentRun?.repoUrl ?? cfg.targetRepo;
  const startingRef =
    currentRun?.commitSha ?? currentRun?.ref ?? cfg.startingRef;
  if (!targetRepo) {
    throw new Error(
      "No target repo: set OPENFIX_TARGET_REPO, or run in GitHub Actions, or ingest with repo context.",
    );
  }

  const prompt = buildRemediationPrompt(finding);
  const slug = options.streamLabel ?? findingSlug(finding.ruleId);
  const verbose = Boolean(options.verbose);
  const quiet = options.quiet ?? !verbose;
  const emit = options.onPhase;

  const log = (msg: string) => {
    if (quiet) return;
    if (verbose) console.log(`[${slug}] ${msg}`);
    else console.log(msg);
  };

  let agentId = "";
  let runId = "";

  try {
    emit?.("starting");

    // Cloud runtime: clone target repo at scanned SHA/ref when known.
    await using agent = await Agent.create({
      apiKey: cfg.apiKey,
      model: { id: cfg.model },
      cloud: {
        repos: [{ url: targetRepo, startingRef }],
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
      openfixRunId,
      status: "started",
      startedAt: new Date().toISOString(),
    };
    await upsertRemediation(started);
    log(`Started agent=${agentId} run=${runId} finding=${finding.id}`);
    emit?.("running");

    // --verbose: stream assistant text with finding-slug prefix.
    // Board mode: do not dump PR markdown into the terminal.
    if (verbose) {
      const streamOut = createLabeledStreamWriter(slug);
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
    } else {
      // Drain stream so the run progresses; optionally surface a short hint.
      for await (const event of run.stream()) {
        if (event.type === "assistant") {
          for (const block of event.message.content) {
            if (block.type === "text" && block.text) {
              const hint = shortAssistantHint(block.text);
              if (hint) emit?.("running", { detail: hint });
            }
          }
        }
      }
    }

    emit?.("opening_pr");

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

    if (finished.status === "finished") {
      emit?.("finished", { prUrl: finished.prUrl });
    } else if (finished.status === "error") {
      emit?.("error", { detail: finished.error });
    } else {
      emit?.("cancelled");
    }

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
        openfixRunId,
        status: "error",
        startedAt: new Date().toISOString(),
        finishedAt: new Date().toISOString(),
        error: `startup failed: ${err.message} (retryable=${err.isRetryable})`,
      };
      await upsertRemediation(failed);
      emit?.("error", { detail: failed.error });
      throw err;
    }
    emit?.("error", {
      detail: err instanceof Error ? err.message : String(err),
    });
    throw err;
  }
}

/** First short sentence from assistant text for board STATUS hint. */
function shortAssistantHint(text: string): string | undefined {
  const cleaned = text.replace(/\s+/g, " ").trim();
  if (cleaned.length < 12) return undefined;
  // Skip markdown-heavy dumps
  if (cleaned.includes("|---") || cleaned.includes("```")) return undefined;
  if (/^#{1,3}\s/.test(cleaned) || cleaned.includes("**PR:**")) return undefined;
  const sentence = cleaned.split(/(?<=[.!?])\s+/)[0] ?? cleaned;
  if (sentence.length < 12) return undefined;
  return sentence.length > 40 ? sentence.slice(0, 39) + "…" : sentence;
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
