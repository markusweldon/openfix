/**
 * Pre-merge verification for remediation PRs.
 *
 * The agent proposes a fix; App CI on the fix PR is the system of record.
 * OpenFix observes checks via `gh` — it does not re-scan or self-attest.
 *
 * Default output is compact (PR + App CI poll). Use --checklist for the full
 * human / branch-protection gate list.
 */
import { execFile } from "node:child_process";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);

/** Long-form pre-merge gates (opt-in via --checklist). */
export function printVerifyChecklist(prUrl?: string): void {
  console.log(`OpenFix pre-merge checklist
==========================
Remediation PRs are not merge-ready when the agent finishes.
They must clear the same gates as any other enterprise change.

${prUrl ? `PR under review: ${prUrl}\n` : ""}Required before merge
--------------------
[ ] 1. Agent-local checks (done in Cursor cloud VM)
      - Regression test added/updated when practical
      - Agent ran project tests (e.g. npm test) and reported results in PR

[ ] 2. PR CI (branch protection — system of record)
      - Open the fix PR → Checks: workflow **CI** (Unit tests + Scanner re-run)
      - Unit tests PASS on the fix branch

[ ] 3. Deterministic scanner re-run on the FIX PR (not the agent claiming "fixed")
      - Same Semgrep / OSV / CodeQL / Snyk jobs as feature PRs
      - Prototype: stub jobs on openfix-vulnerable-app named like real scanners
      - Do NOT trust agent prose alone — require scanner evidence

[ ] 4. Human authorization
      - AppSec / eng reviewed Diff + OpenFix provenance block
      - human_only findings (secrets/critical/auth) were NOT auto-merged by bots
      - No force-push; no direct push to main (hooks + branch protection)

[ ] 5. Merge only after 1–4
      - OpenFix never auto-merges

Branch protection checklist (target repo settings)
-------------------------------------------------
[ ] Require pull request before merging
[ ] Require status checks to pass (test + scanner workflows)
[ ] Require conversation resolution / review from CODEOWNERS as needed
[ ] Block force pushes to main
[ ] Restrict who can push to main

Where OpenFix itself runs in CI
-------------------------------
  Repo workflow: "OpenFix: SARIF → fix PRs" (manual Run workflow)
  = production placement of ingest → triage → Cursor remediate
  Local path is the same code: openfix remediate
`);
}

interface GhPrCheck {
  name: string;
  state: string;
  bucket: "pass" | "fail" | "pending" | "skipping" | "cancel" | string;
  workflow?: string;
  link?: string;
}

export type VerifyChecksOutcome =
  | { kind: "skipped"; reason: string }
  | { kind: "polled"; checks: GhPrCheck[]; failed: boolean; pending: boolean };

function bucketFromConclusion(
  conclusion: string | null,
  status: string,
): GhPrCheck["bucket"] {
  if (status !== "completed") return "pending";
  switch (conclusion) {
    case "success":
      return "pass";
    case "failure":
    case "timed_out":
    case "action_required":
      return "fail";
    case "cancelled":
      return "cancel";
    case "skipped":
    case "neutral":
      return "skipping";
    default:
      return "pending";
  }
}

function glyphForBucket(bucket: string): string {
  switch (bucket) {
    case "pass":
      return "✓";
    case "fail":
    case "cancel":
      return "✗";
    case "skipping":
      return "–";
    default:
      return "…";
  }
}

/** Prefer commit check-runs (works for workflow_dispatch + pull_request). */
async function pollViaCheckRuns(prUrl: string): Promise<GhPrCheck[]> {
  const { stdout: meta } = await execFileAsync(
    "gh",
    ["pr", "view", prUrl, "--json", "headRefOid,headRepository"],
    { timeout: 30_000 },
  );
  const parsed = JSON.parse(meta) as {
    headRefOid: string;
    headRepository?: { nameWithOwner?: string };
  };
  const sha = parsed.headRefOid;
  const repo = parsed.headRepository?.nameWithOwner;
  if (!sha) return [];

  const repoFromUrl = prUrl.match(/github\.com\/([^/]+\/[^/]+)/)?.[1];
  const { stdout } = await execFileAsync(
    "gh",
    [
      "api",
      `repos/${repoFromUrl ?? repo}/commits/${sha}/check-runs?per_page=100`,
      "--jq",
      ".check_runs",
    ],
    { timeout: 30_000, maxBuffer: 4 * 1024 * 1024 },
  );

  const runs = JSON.parse(stdout) as Array<{
    name: string;
    status: string;
    conclusion: string | null;
    html_url?: string;
    app?: { slug?: string };
  }>;

  // Deduplicate by name (keep last) — prefer github-actions
  const byName = new Map<string, GhPrCheck>();
  for (const r of runs) {
    if (r.app?.slug && r.app.slug !== "github-actions") continue;
    byName.set(r.name, {
      name: r.name,
      state: r.status,
      bucket: bucketFromConclusion(r.conclusion, r.status),
      link: r.html_url,
    });
  }
  return [...byName.values()].sort((a, b) => a.name.localeCompare(b.name));
}

/** Poll App CI on the fix PR via GitHub CLI (observes checks; does not re-scan). */
export async function pollPrChecks(prUrl: string): Promise<VerifyChecksOutcome> {
  try {
    let checks: GhPrCheck[] = [];
    try {
      checks = await pollViaCheckRuns(prUrl);
    } catch {
      // fall through to gh pr checks
    }

    if (checks.length === 0) {
      try {
        const { stdout } = await execFileAsync(
          "gh",
          ["pr", "checks", prUrl, "--json", "name,state,bucket,workflow,link"],
          { timeout: 30_000, maxBuffer: 2 * 1024 * 1024 },
        );
        checks = JSON.parse(stdout) as GhPrCheck[];
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : String(err);
        const stderr =
          err && typeof err === "object" && "stderr" in err
            ? String((err as { stderr: unknown }).stderr)
            : "";
        if (!/no checks reported/i.test(`${message}\n${stderr}`)) {
          throw err;
        }
      }
    }

    const failed = checks.some(
      (c) => c.bucket === "fail" || c.bucket === "cancel",
    );
    const pending =
      checks.length === 0 || checks.some((c) => c.bucket === "pending");
    return { kind: "polled", checks, failed, pending };
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : String(err);
    const stderr =
      err && typeof err === "object" && "stderr" in err
        ? String((err as { stderr: unknown }).stderr)
        : "";
    const combined = `${message}\n${stderr}`;

    const reason = /ENOENT|not found/i.test(combined)
      ? "gh CLI not found — install GitHub CLI to poll App CI checks"
      : `could not poll PR checks (${stderr.trim() || message.split("\n")[0]})`;
    return { kind: "skipped", reason };
  }
}

/** Compact App CI section (default verify output). */
export function printPrChecksReport(outcome: VerifyChecksOutcome): void {
  console.log("  App CI");
  if (outcome.kind === "skipped") {
    console.log(`    (skipped) ${outcome.reason}`);
    console.log("    Open the PR Checks tab in the browser if needed.");
    return;
  }

  if (outcome.checks.length === 0) {
    console.log("    …  No checks reported yet");
    console.log("\n  Result  PENDING — re-run verify shortly");
    return;
  }

  for (const c of outcome.checks) {
    const g = glyphForBucket(c.bucket);
    const suffix =
      c.bucket === "pending"
        ? "  pending"
        : c.bucket === "fail" || c.bucket === "cancel"
          ? `  ${c.bucket}`
          : "";
    console.log(`    ${g}  ${c.name}${suffix}`);
  }

  if (outcome.failed) {
    console.log("\n  Result  FAIL — one or more App CI checks failed");
  } else if (outcome.pending) {
    console.log("\n  Result  PENDING — re-run verify shortly");
  } else {
    console.log("\n  Result  PASS");
    console.log("  Next    Human review + merge (OpenFix never auto-merges)");
  }
}

export interface RunVerifyOptions {
  /** Print the long static pre-merge / branch-protection checklist. */
  checklist?: boolean;
}

/**
 * Verify: compact App CI poll by default; optional --checklist essay.
 * Returns recommended process.exitCode (0 or 1).
 */
export async function runVerify(
  prUrl?: string,
  options: RunVerifyOptions = {},
): Promise<number> {
  const showChecklist = Boolean(options.checklist);

  console.log("\n── OpenFix verify ──");

  if (showChecklist) {
    printVerifyChecklist(prUrl);
  }

  if (!prUrl) {
    console.log("  (pass --pr <url> or --last to poll App CI)");
    if (!showChecklist) {
      console.log("  Tip: full pre-merge checklist → verify --checklist");
    }
    console.log("");
    return 0;
  }

  console.log(`  PR  ${prUrl}\n`);

  const outcome = await pollPrChecks(prUrl);
  printPrChecksReport(outcome);
  console.log("");

  if (outcome.kind === "skipped") return 0;
  if (outcome.failed) return 1;
  return 0; // pass or pending — pending stays 0 so mid-CI is not flaky
}
