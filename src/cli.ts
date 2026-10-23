#!/usr/bin/env node
/**
 * OpenFix CLI — control plane for the remediation pipeline.
 *
 * Commands:
 *   ingest    → SARIF/JSON path(s) (merge + fingerprint dedupe), or --from simulated:…;
 *               writes OpenFix run context (repo / SHA / run id) under .openfix/
 *   triage    → deterministic policy (no agents) — reads policy.yaml; prints run line
 *   remediate → Cursor cloud agents open fix PRs (finding-lane board by default)
 *   status    → inspect durable agent by bc-… id (async)
 *   resume    → follow-up turn on same agent (multi-step)
 *   verify    → poll App CI on the fix PR (via gh); optional --checklist
 *
 * Same logic can run from a GitHub Action on SARIF upload; the CLI is the
 * prototype control plane and live demo surface.
 */
import { Command } from "commander";
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
  type OpenFixRun,
  type IngestSource,
} from "./state/store.js";
import { getConfig } from "./config.js";
import {
  remediateFinding,
  statusAgent,
  resumeAgent,
} from "./remediator/agent.js";
import { runVerify } from "./verify.js";
import { loadFindingsWithSource } from "./ingest/load.js";
import {
  loadSimulatedMcpFindings,
  parseSimulatedFromSpec,
} from "./ingest/simulated-mcp.js";
import {
  parseAgentId,
  printFleetSummary,
  printFleetNextSteps,
  LaneBoard,
  findingLocation,
  uniqueFindingSlugs,
  type FleetRow,
} from "./cli/helpers.js";
import type { Finding, TriageResult } from "./types/finding.js";

const program = new Command();

program
  .name("openfix")
  .description(
    "Legacy Cursor adapter. Use the OpenFix v0.2 CLI for cases, enrichment, validation and review.",
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

function buildRunFromConfig(source: IngestSource): OpenFixRun {
  const cfg = getConfig();
  return {
    openfixRunId: cfg.openfixRunId,
    repoUrl: cfg.targetRepo,
    commitSha: cfg.commitSha,
    ref: cfg.startingRef,
    source,
    createdAt: new Date().toISOString(),
  };
}

async function detectFileSource(
  filePath: string,
): Promise<{ findings: Finding[]; source: IngestSource }> {
  const { findings, kind } = await loadFindingsWithSource(filePath);
  return { findings, source: { kind, detail: filePath } };
}

function printIngestSummary(
  findings: Finding[],
  run: OpenFixRun,
  runFileHint?: string,
  dedupe?: { raw: number; dropped: number },
): void {
  console.log(`Ingested ${findings.length} finding(s) [${run.source.kind}]`);
  if (dedupe && dedupe.dropped > 0) {
    console.log(
      `  dedupe        kept ${findings.length} · dropped ${dedupe.dropped} duplicate fingerprint(s) (of ${dedupe.raw})`,
    );
  }
  console.log(`  openfixRunId  ${run.openfixRunId}`);
  if (run.repoUrl) console.log(`  repoUrl       ${run.repoUrl}`);
  if (run.commitSha) console.log(`  commitSha     ${run.commitSha}`);
  console.log(`  source        ${run.source.kind}: ${run.source.detail}`);
  if (runFileHint) console.log(`  run file      ${runFileHint}`);
  for (const f of findings) {
    console.log(
      `  - [${f.severity}] ${f.tool}/${f.ruleId} ${f.file ?? "?"}${f.startLine ? `:${f.startLine}` : ""} (${f.fingerprint})`,
    );
  }
}

/** First-wins dedupe by fingerprint (exact re-uploads / overlapping artifacts). */
function dedupeByFingerprint(findings: Finding[]): {
  findings: Finding[];
  raw: number;
  dropped: number;
} {
  const seen = new Set<string>();
  const out: Finding[] = [];
  for (const f of findings) {
    if (seen.has(f.fingerprint)) continue;
    seen.add(f.fingerprint);
    out.push(f);
  }
  return {
    findings: out,
    raw: findings.length,
    dropped: findings.length - out.length,
  };
}

// --- ingest: scanners → local state ---
program
  .command("ingest")
  .description(
    "Ingest SARIF/JSON path(s), or --from simulated:semgrep|snyk (MCP-style adapter stub)",
  )
  .argument(
    "[paths...]",
    "One or more SARIF / findings JSON paths (merged + fingerprint-deduped)",
  )
  .option(
    "--from <spec>",
    "Adapter ingest: simulated:semgrep | simulated:snyk | mcp:semgrep | mcp:snyk",
  )
  .action(async (paths: string[], opts: { from?: string }) => {
    let findings: Finding[];
    let source: IngestSource;
    let dedupe: { raw: number; dropped: number } | undefined;

    if (opts.from) {
      if (paths.length > 0) {
        console.error("Use either file path(s) or --from, not both.");
        process.exitCode = 1;
        return;
      }
      const scanner = parseSimulatedFromSpec(opts.from);
      if (!scanner) {
        console.error(
          `Unknown --from ${opts.from}. Use simulated:semgrep, simulated:snyk, mcp:semgrep, or mcp:snyk.`,
        );
        process.exitCode = 1;
        return;
      }
      findings = loadSimulatedMcpFindings(scanner);
      source = {
        kind: opts.from.toLowerCase().includes("mcp") ? "mcp" : "simulated",
        detail: opts.from,
      };
    } else if (paths.length > 0) {
      const merged: Finding[] = [];
      const kinds: Array<"sarif" | "json"> = [];
      for (const p of paths) {
        const loaded = await detectFileSource(p);
        merged.push(...loaded.findings);
        kinds.push(loaded.source.kind as "sarif" | "json");
      }
      const deduped = dedupeByFingerprint(merged);
      findings = deduped.findings;
      dedupe = { raw: deduped.raw, dropped: deduped.dropped };
      source = {
        kind: kinds.includes("sarif") ? "sarif" : "json",
        detail: paths.join(", "),
      };
    } else {
      console.error(
        "Pass SARIF/JSON path(s), or --from simulated:semgrep (see --help).",
      );
      process.exitCode = 1;
      return;
    }

    const run = buildRunFromConfig(source);
    await saveFindings(findings, run);
    printIngestSummary(
      findings,
      run,
      `.openfix/runs/${run.openfixRunId}.json`,
      dedupe,
    );
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
    if (state.currentRun) {
      const r = state.currentRun;
      console.log(
        `\nOpenFix run  ${r.openfixRunId}` +
          (r.repoUrl ? `  repo=${r.repoUrl}` : "") +
          (r.commitSha ? `  sha=${r.commitSha.slice(0, 7)}` : "") +
          `  source=${r.source.kind}`,
      );
    }
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
  .option("--all-auto", "Start one batch up to OPENFIX_MAX_CONCURRENT")
  .option("--fingerprint <fp>", "Remediate a single finding by fingerprint")
  .option(
    "--verbose",
    "Stream full agent assistant text (finding-slug labels); disable lane board",
  )
  .action(
    async (opts: {
      agents?: number;
      allAuto?: boolean;
      fingerprint?: string;
      verbose?: boolean;
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
      const verbose = Boolean(opts.verbose);
      const useBoard = !verbose;

      const slugs = uniqueFindingSlugs(batch.map((r) => r.finding));

      console.log(
        `\n── OpenFix remediate ──  ${batch.length} lane${batch.length === 1 ? "" : "s"} · ${queue.length} eligible · ${remainingAfter} remain after\n`,
      );

      let board: LaneBoard | undefined;
      if (useBoard) {
        board = new LaneBoard(
          batch.map((r, i) => ({
            id: r.finding.fingerprint,
            severity: r.finding.severity,
            finding: slugs[i]!,
            location: findingLocation(r.finding),
          })),
          remainingAfter,
        );
        board.start();
      } else {
        for (const [i, r] of batch.entries()) {
          console.log(
            `  ${r.finding.severity.padEnd(8)} ${slugs[i]!.padEnd(20)} ${findingLocation(r.finding)}`,
          );
        }
        if (remainingAfter > 0) {
          console.log(
            `  … ${remainingAfter} more queued (severity-ordered)`,
          );
        }
        console.log("");
      }

      const fleetRows: FleetRow[] = [];
      let settled: PromiseSettledResult<{
        label: string;
        fingerprint: string;
        ruleId: string;
        record: Awaited<ReturnType<typeof remediateFinding>>;
      }>[] = [];

      try {
        settled = await Promise.allSettled(
          batch.map(async (r, i) => {
            const slug = slugs[i]!;
            const fp = r.finding.fingerprint;
            const record = await remediateFinding(r.finding, {
              streamLabel: slug,
              verbose,
              quiet: useBoard,
              suppressNextSteps: true,
              onPhase: board
                ? (phase, meta) => board.setPhase(fp, phase, meta)
                : undefined,
            });
            return {
              label: slug,
              fingerprint: fp,
              ruleId: `${r.finding.tool}/${r.finding.ruleId}`,
              record,
            };
          }),
        );
      } finally {
        board?.finish();
      }

      for (const [i, outcome] of settled.entries()) {
        const r = batch[i]!;
        const label = slugs[i]!;
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

      printFleetSummary(fleetRows, remainingAfter);
      printFleetNextSteps(fleetRows);

      // Fail CLI/CI on startup throws, mid-run error/cancel, or finished-with-no-PR.
      const rejected = settled.some((s) => s.status === "rejected");
      const badRecord = fleetRows.some(
        (row) => row.status !== "finished" || !row.prUrl,
      );
      if (rejected || badRecord) {
        const reasons: string[] = [];
        if (rejected) reasons.push("one or more agents threw at startup");
        for (const row of fleetRows) {
          if (row.status !== "finished") {
            reasons.push(
              `${row.label} status=${row.status}${row.error ? ` (${row.error})` : ""}`,
            );
          } else if (!row.prUrl) {
            reasons.push(`${row.label} finished but no PR URL`);
          }
        }
        console.error(
          `\nRemediate failed — orchestrator exiting non-zero:\n  - ${reasons.join("\n  - ")}`,
        );
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

// --- verify: observe App CI on the fix PR ---
program
  .command("verify")
  .description(
    "Poll App CI checks on the fix PR (via gh); optional full pre-merge checklist",
  )
  .option("--pr <url>", "Remediation PR URL to verify")
  .option("--last", "Use lastPrUrl from .openfix/state.json")
  .option(
    "--checklist",
    "Print the full pre-merge / branch-protection checklist",
  )
  .action(async (opts: { pr?: string; last?: boolean; checklist?: boolean }) => {
    let pr = opts.pr;
    if (opts.last && !pr) pr = await getLastPrUrl();
    process.exitCode = await runVerify(pr, { checklist: opts.checklist });
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

