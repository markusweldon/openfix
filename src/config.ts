/**
 * Config from environment / .env (never commit secrets).
 *
 * CURSOR_API_KEY       — required for cloud remediate/status/resume
 * OPENFIX_TARGET_REPO  — GitHub URL the cloud agent clones
 * OPENFIX_STARTING_REF — usually main
 * OPENFIX_MODEL        — default composer-2.5
 * OPENFIX_MAX_CONCURRENT — cap parallel agents (--all-auto)
 */
import { config as loadDotenv } from "dotenv";

loadDotenv({ quiet: true });

export interface OpenFixConfig {
  apiKey: string | undefined;
  targetRepo: string | undefined;
  startingRef: string;
  model: string;
  maxConcurrent: number;
}

export function getConfig(): OpenFixConfig {
  const max = Number.parseInt(process.env.OPENFIX_MAX_CONCURRENT ?? "2", 10);
  return {
    apiKey: process.env.CURSOR_API_KEY,
    targetRepo: process.env.OPENFIX_TARGET_REPO,
    startingRef: process.env.OPENFIX_STARTING_REF ?? "main",
    model: process.env.OPENFIX_MODEL ?? "composer-2.5",
    maxConcurrent: Number.isFinite(max) && max > 0 ? max : 2,
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
      "OPENFIX_TARGET_REPO is required (GitHub URL for the cloud agent to clone). See .env.example.",
    );
  }
  return { ...cfg, apiKey: cfg.apiKey, targetRepo: cfg.targetRepo };
}
