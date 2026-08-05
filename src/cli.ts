#!/usr/bin/env node
/**
 * OpenFix CLI — demo harness for the remediation pipeline.
 *
 * Commands map 1:1 to the interview story:
 *   ingest    → load SARIF / findings JSON (detection plane)
 *   triage    → deterministic policy (no agents) — reads policy.yaml
 *   remediate → Cursor cloud agents open fix PRs (remediation lane)
 *   status    → inspect durable agent by bc-… id (async)
 *   resume    → follow-up turn on same agent (multi-step)
 *   verify    → pre-merge checklist (CI + scanner re-run + human)
 *
 * Enterprise scale: same logic would run from a GitHub Action on SARIF upload;
 * CLI is the prototype control plane, not the final UX.
 */
import { Command } from "commander";
import { loadFindings } from "./ingest/load.js";
import {
  triageAll,
  summarizeTriage,
  prioritizeAutoFix,
} from "./policy/engine.js";
import {
  saveFindings,
  loadState,
  inFlightFingerprints,
  getLastAgentId,
  getLastPrUrl,
} from "./state/store.js";
import { getConfig } from "./config.js";
import {
  remediateFinding,
  statusAgent,
  resumeAgent,
} from "./remediator/agent.js";
import { printVerifyChecklist } from "./verify.js";
import {
  parseAgentId,
  printFleetSummary,
  printNextSteps,
  type FleetRow,
} from "./cli/helpers.js";
import type { TriageResult } from "./types/finding.js";

const program = new Command();

program
  .name("openfix")
  .description(
    "Scanner findings in. Cursor agents remediate. PRs out for human review.",
  )
  .version("0.1.0");

async function resolveAgentId(
  agentIdArg: string | undefined,
  useLast: boolean | undefined,
): Promise<string> {
  if (useLast) return getLastAgentId();
  if (!agentIdArg) {
    throw new Error("Pass a bc-… agent id, or use --last");
  }
  return parseAgentId(agentIdArg);
}

// --- ingest: scanners → local state ---
program
  .command("ingest")
  .description("Ingest SARIF or OpenFix findings JSON into local state")
  .argument("<path>", "Path to SARIF (.sarif/.json) or findings JSON")
  .action(async (path: string) => {
    const findings = await loadFindings(path);
    await saveFindings(findings);
    console.log(`Ingested ${findings.length} finding(s) from ${path}`);
    for (const f of findings) {
      console.log(
        `  - [${f.severity}] ${f.tool}/${f.ruleId} ${f.file ?? "?"}${f.startLine ? `:${f.startLine}` : ""} (${f.fingerprint})`,
      );
    }
  });

// --- triage: policy only (great place to pause and talk in the demo) ---
program
  .command("triage")
  .description(
    "Apply deterministic policy (policy.yaml) to ingested findings — no agents",
  )
  .action(async () => {
    const state = await loadState();
    if (state.findings.length === 0) {
      console.error("No findings ingested. Run: openfix ingest <path>");
      process.exitCode = 1;
      return;
    }
    const results = triageAll(state.findings, {
      inFlightFingerprints: inFlightFingerprints(state),
    });
    printTriage(results);
    console.log("\nSummary:", summarizeTriage(results));
    console.log("(policy source: ./policy.yaml — edit to live-extend)");
  });

// --- remediate: only auto_fix queue, highest severity first ---
program
  .command("remediate")
  .description("Spawn Cursor cloud agents for auto_fix findings (opens PRs)")
  .option(
    "-n, --agents <count>",
    "Spawn up to N concurrent agents (capped by queue + OPENFIX_MAX_CONCURRENT)",
    (v) => Number.parseInt(v, 10),
  )
  .option("--all-auto", "Drain auto_fix queue up to OPENFIX_MAX_CONCURRENT")
  .option("--fingerprint <fp>", "Remediate a single finding by fingerprint")
  .action(
    async (opts: {
      agents?: number;
      allAuto?: boolean;
      fingerprint?: string;
    }) => {
      const state = await loadState();
      if (state.findings.length === 0) {
        console.error("No findings ingested. Run: openfix ingest <path>");
        process.exitCode = 1;
        return;
      }

      const results = triageAll(state.findings, {
        inFlightFingerprints: inFlightFingerprints(state),
      });
      let queue = prioritizeAutoFix(results);

      if (opts.fingerprint) {
        queue = queue.filter(
          (r) => r.finding.fingerprint === opts.fingerprint,
        );
        if (queue.length === 0) {
          console.error(
            `No auto_fix finding with fingerprint ${opts.fingerprint}`,
          );
          process.exitCode = 1;
          return;
        }
      }

      if (queue.length === 0) {
        console.log(
          "No auto_fix findings left in queue (all suppressed, human_only, or already remediating).",
        );
        console.log("Summary:", summarizeTriage(results));
        return;
      }

      const cfg = getConfig();
      let want = 1;
      if (opts.allAuto) want = cfg.maxConcurrent;
      if (opts.agents != null) {
        if (!Number.isFinite(opts.agents) || opts.agents < 1) {
          console.error("--agents / -n must be a positive integer");
          process.exitCode = 1;
          return;
        }
        want = opts.agents;
      }
      const batchSize = Math.min(want, queue.length, cfg.maxConcurrent);
      const batch = queue.slice(0, batchSize);
      const remainingAfter = Math.max(0, queue.length - batch.length);
      const concurrent = batch.length > 1;

      console.log(`
── OpenFix remediate ──
  Scale story: SARIF is per app; this lane runs in each repo's pipeline.
  Concurrency here = factory fan-out inside one app's queue (not a multi-repo router).
`);
      console.log(
        `Auto-fix queue: ${queue.length} eligible (ordered by severity, highest first)`,
      );
      for (const [i, r] of queue.entries()) {
        const marker = i < batch.length ? "NEXT" : "queued";
        console.log(
          `  [${marker}] ${r.finding.severity.padEnd(8)} ${r.finding.tool}/${r.finding.ruleId}`,
        );
        console.log(
          `           ${r.finding.file ?? "?"}${r.finding.startLine ? `:${r.finding.startLine}` : ""}  fp=${r.finding.fingerprint}`,
        );
      }
      console.log(
        `\nThis run: ${batch.length} concurrent agent(s) (requested=${want}, maxConcurrent=${cfg.maxConcurrent}); ${remainingAfter} left in queue after`,
      );

      const fleetRows: FleetRow[] = [];
      const settled = await Promise.allSettled(
        batch.map(async (r, i) => {
          const label = concurrent ? `A${i + 1}` : undefined;
          const record = await remediateFinding(r.finding, {
            streamLabel: label,
            suppressNextSteps: concurrent,
          });
          return {
            label: label ?? "A1",
            fingerprint: r.finding.fingerprint,
            ruleId: `${r.finding.tool}/${r.finding.ruleId}`,
            record,
          };
        }),
      );

      for (const [i, outcome] of settled.entries()) {
        const r = batch[i]!;
        const label = concurrent ? `A${i + 1}` : "A1";
        if (outcome.status === "fulfilled") {
          const { record } = outcome.value;
          fleetRows.push({
            label,
            fingerprint: outcome.value.fingerprint,
            ruleId: outcome.value.ruleId,
            status: record.status,
            agentId: record.agentId,
            prUrl: record.prUrl,
            error: record.error,
          });
        } else {
          const message =
            outcome.reason instanceof Error
              ? outcome.reason.message
              : String(outcome.reason);
          fleetRows.push({
            label,
            fingerprint: r.finding.fingerprint,
            ruleId: `${r.finding.tool}/${r.finding.ruleId}`,
            status: "error",
            error: message,
          });
        }
      }

      if (concurrent) {
        printFleetSummary(fleetRows);
        const lastOk = [...fleetRows]
          .reverse()
          .find((row) => row.agentId && row.agentId !== "unknown");
        if (lastOk?.agentId) printNextSteps(lastOk.agentId, lastOk.prUrl);
      }

      if (settled.some((s) => s.status === "rejected")) {
        process.exitCode = 1;
      }
    },
  );

// --- status / resume: async + multi-step SDK story ---
program
  .command("status")
  .description("Inspect a Cursor agent by id (or --last)")
  .argument("[agentId]", "Cloud agent id (bc-...) — optional with --last")
  .option("--last", "Use lastAgentId from .openfix/state.json")
  .action(async (agentId: string | undefined, opts: { last?: boolean }) => {
    const id = await resolveAgentId(agentId, opts.last);
    console.log(`status → ${id}`);
    await statusAgent(id);
  });

program
  .command("resume")
  .description("Send a follow-up prompt to an existing agent (or --last)")
  .argument("[agentId]", "Cloud agent id (bc-...) — optional with --last")
  .requiredOption("--prompt <text>", "Follow-up instruction")
  .option("--last", "Use lastAgentId from .openfix/state.json")
  .action(
    async (
      agentId: string | undefined,
      opts: { prompt: string; last?: boolean },
    ) => {
      const id = await resolveAgentId(agentId, opts.last);
      console.log(`resume → ${id}`);
      await resumeAgent(id, opts.prompt);
    },
  );

// --- verify: what must pass before a human merges the fix PR ---
program
  .command("verify")
  .description(
    "Print pre-merge verification checklist (CI + scanner re-run + human review)",
  )
  .option("--pr <url>", "Remediation PR URL to attach to the checklist")
  .option("--last", "Use lastPrUrl from .openfix/state.json")
  .action(async (opts: { pr?: string; last?: boolean }) => {
    let pr = opts.pr;
    if (opts.last && !pr) pr = await getLastPrUrl();
    printVerifyChecklist(pr);
  });

/** Pretty-print triage buckets; auto_fix list is severity-sorted (the queue). */
function printTriage(results: TriageResult[]): void {
  const order = ["auto_fix", "human_only", "suppress_noise"] as const;
  for (const decision of order) {
    let group = results.filter((r) => r.decision === decision);
    if (decision === "auto_fix") {
      group = prioritizeAutoFix(results);
    }
    if (group.length === 0) continue;
    console.log(`\n## ${decision} (${group.length})`);
    if (decision === "auto_fix") {
      console.log("  (ordered highest severity first — this is the remediate queue)");
    }
    for (const r of group) {
      console.log(
        `  [${r.finding.severity}] ${r.finding.tool}/${r.finding.ruleId}`,
      );
      console.log(
        `    ${r.finding.file ?? "(no file)"}${r.finding.startLine ? `:${r.finding.startLine}` : ""}`,
      );
      console.log(`    fingerprint=${r.finding.fingerprint}`);
      console.log(`    reasons: ${r.reasons.join("; ")}`);
    }
  }
}

program.parseAsync(process.argv).catch((err: unknown) => {
  const message = err instanceof Error ? err.message : String(err);
  console.error(message);
  process.exitCode = 1;
});
