/**
 * Config from environment / .env (never commit secrets).
 *
 * Resolution order for repo / ref / SHA:
 *   1. Explicit OPENFIX_* overrides
 *   2. GitHub Actions GITHUB_* when present
 *   3. Fail clearly when cloud remediate needs a repo and none is set
 *
 * CURSOR_API_KEY         — required for cloud remediate/status/resume
 * OPENFIX_TARGET_REPO    — explicit GitHub URL (local demo / cross-repo)
 * OPENFIX_STARTING_REF   — branch or SHA for the agent clone
 * OPENFIX_COMMIT_SHA     — scanned commit (binds findings to a snapshot)
 * OPENFIX_MODEL          — default composer-2.5
 * OPENFIX_MAX_CONCURRENT — cap parallel agents (--all-auto)
 */
import { config as loadDotenv } from "dotenv";
import { randomUUID } from "node:crypto";

loadDotenv({ quiet: true });

export interface OpenFixConfig {
  apiKey: string | undefined;
  targetRepo: string | undefined;
  startingRef: string;
  /** Scanned commit SHA when known (pipeline or OPENFIX_COMMIT_SHA). */
  commitSha: string | undefined;
  /** Pipeline / local OpenFix job id (GITHUB_RUN_ID or generated). */
  openfixRunId: string;
  model: string;
  maxConcurrent: number;
  /** True when running inside GitHub Actions. */
  inGitHubActions: boolean;
}

function deriveRepoFromGitHub(): string | undefined {
  const server = (process.env.GITHUB_SERVER_URL ?? "https://github.com").replace(
    /\/$/,
    "",
  );
  const repo = process.env.GITHUB_REPOSITORY?.trim();
  if (!repo) return undefined;
  return `${server}/${repo}`;
}

function deriveRefFromGitHub(): string | undefined {
  // PR builds: head branch; otherwise short ref name or full SHA
  const head = process.env.GITHUB_HEAD_REF?.trim();
  if (head) return head;
  const refName = process.env.GITHUB_REF_NAME?.trim();
  if (refName) return refName;
  return undefined;
}

function deriveRunId(): string {
  const gh = process.env.GITHUB_RUN_ID?.trim();
  const attempt = process.env.GITHUB_RUN_ATTEMPT?.trim();
  if (gh) return attempt && attempt !== "1" ? `${gh}.${attempt}` : gh;
  return `local-${randomUUID()}`;
}

export function getConfig(): OpenFixConfig {
  const max = Number.parseInt(process.env.OPENFIX_MAX_CONCURRENT ?? "2", 10);
  const inGitHubActions = Boolean(process.env.GITHUB_ACTIONS);

  const explicitRepo = process.env.OPENFIX_TARGET_REPO?.trim() || undefined;
  const targetRepo = explicitRepo ?? deriveRepoFromGitHub();

  const explicitSha = process.env.OPENFIX_COMMIT_SHA?.trim() || undefined;
  const commitSha =
    explicitSha ?? (process.env.GITHUB_SHA?.trim() || undefined);

  const explicitRef = process.env.OPENFIX_STARTING_REF?.trim() || undefined;
  // Prefer explicit ref; else SHA when known (pin agent to scanned snapshot); else GH ref; else main
  const startingRef =
    explicitRef ?? commitSha ?? deriveRefFromGitHub() ?? "main";

  return {
    apiKey: process.env.CURSOR_API_KEY,
    targetRepo,
    startingRef,
    commitSha,
    openfixRunId: process.env.OPENFIX_RUN_ID?.trim() || deriveRunId(),
    model: process.env.OPENFIX_MODEL ?? "composer-2.5",
    maxConcurrent: Number.isFinite(max) && max > 0 ? max : 2,
    inGitHubActions,
  };
}

/** Hard-fail before spending time on Agent.create without credentials/repo. */
export function requireCloudConfig(): OpenFixConfig & {
  apiKey: string;
  targetRepo: string;
} {
  const cfg = getConfig();
  if (!cfg.apiKey) {
    throw new Error(
      "CURSOR_API_KEY is required for cloud remediation. Set it in .env (see .env.example).",
    );
  }
  if (!cfg.targetRepo) {
    throw new Error(
      "No target repo: set OPENFIX_TARGET_REPO, or run in GitHub Actions (GITHUB_REPOSITORY).",
    );
  }
  return { ...cfg, apiKey: cfg.apiKey, targetRepo: cfg.targetRepo };
}
