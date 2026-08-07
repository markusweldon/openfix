/**
 * Policy engine — deterministic triage. No LLM here on purpose.
 *
 * Who gets an agent is decided by policy.yaml, not by the model. Edit the YAML
 * and re-run triage to change gates without touching agent prompts.
 *
 * Three buckets:
 *   auto_fix      → remediate() spawns a Cursor cloud agent
 *   human_only     → AppSec/eng handles (still shown in triage)
 *   suppress_noise → skip (info/note, in-flight fingerprints, etc.)
 */
import { readFileSync, existsSync } from "node:fs";
import path from "node:path";
import { parse as parseYaml } from "yaml";
import type { Finding, Severity, TriageResult } from "../types/finding.js";

export interface OpenFixPolicy {
  critical_always_human: boolean;
  secrets_always_human: boolean;
  iac_always_human: boolean;
  require_file_location: boolean;
  sensitive_path_segments: string[];
  iac_file_extensions: string[];
  iac_dir_segments: string[];
  noise_severities: Severity[];
  sast_auto_fix_severities: Severity[];
  sca_human_severities: Severity[];
}

const DEFAULT_POLICY: OpenFixPolicy = {
  critical_always_human: true,
  secrets_always_human: true,
  iac_always_human: true,
  require_file_location: true,
  sensitive_path_segments: [
    "auth",
    "crypto",
    "iam",
    "secret",
    "secrets",
    "password",
    "credential",
    "oauth",
    "jwt",
  ],
  iac_file_extensions: [".tf", ".tfvars"],
  iac_dir_segments: [
    "terraform",
    "cloudformation",
    "k8s",
    "kubernetes",
    "helm",
  ],
  noise_severities: ["info", "note"],
  sast_auto_fix_severities: ["high", "medium"],
  sca_human_severities: ["low"],
};

let cachedPolicy: OpenFixPolicy | null = null;
let cachedPolicyPath: string | null = null;

function escapeRegex(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function buildSensitivePathRegex(segments: string[]): RegExp {
  const body = segments.map(escapeRegex).join("|");
  return new RegExp(`(^|/)(${body})(/|$)`, "i");
}

function buildIacDirRegex(segments: string[]): RegExp {
  const body = segments.map(escapeRegex).join("|");
  return new RegExp(`(^|/)(${body})(/|$)`, "i");
}

function isIacFile(file: string, extensions: string[]): boolean {
  const lower = file.toLowerCase();
  return extensions.some((ext) => lower.endsWith(ext.toLowerCase()));
}

/** Load policy.yaml from cwd (or defaults). Cleared cache when path changes. */
export function loadPolicy(cwd = process.cwd()): OpenFixPolicy {
  const policyPath = path.join(cwd, "policy.yaml");
  if (cachedPolicy && cachedPolicyPath === policyPath) {
    // Always re-read in demo so live edits to policy.yaml apply without restart.
  }
  cachedPolicyPath = policyPath;

  if (!existsSync(policyPath)) {
    cachedPolicy = DEFAULT_POLICY;
    return cachedPolicy;
  }

  try {
    const raw = parseYaml(readFileSync(policyPath, "utf8")) as Partial<OpenFixPolicy>;
    cachedPolicy = {
      ...DEFAULT_POLICY,
      ...raw,
      sensitive_path_segments:
        raw.sensitive_path_segments ?? DEFAULT_POLICY.sensitive_path_segments,
      iac_file_extensions:
        raw.iac_file_extensions ?? DEFAULT_POLICY.iac_file_extensions,
      iac_dir_segments: raw.iac_dir_segments ?? DEFAULT_POLICY.iac_dir_segments,
      noise_severities: (raw.noise_severities ??
        DEFAULT_POLICY.noise_severities) as Severity[],
      sast_auto_fix_severities: (raw.sast_auto_fix_severities ??
        DEFAULT_POLICY.sast_auto_fix_severities) as Severity[],
      sca_human_severities: (raw.sca_human_severities ??
        DEFAULT_POLICY.sca_human_severities) as Severity[],
    };
    return cachedPolicy;
  } catch (err) {
    console.error(
      `Warning: failed to parse policy.yaml (${err instanceof Error ? err.message : err}); using defaults.`,
    );
    cachedPolicy = DEFAULT_POLICY;
    return cachedPolicy;
  }
}

/** Force reload on next triage (after live edit). */
export function reloadPolicy(cwd = process.cwd()): OpenFixPolicy {
  cachedPolicy = null;
  cachedPolicyPath = null;
  return loadPolicy(cwd);
}

export interface PolicyOptions {
  /** Fingerprints already started/finished — skip spawning duplicate agents. */
  inFlightFingerprints?: Set<string>;
  /** Override cwd for policy.yaml (tests). */
  cwd?: string;
}

/**
 * Decide what to do with ONE finding.
 * Order matters: noise → dedupe → hard human gates → allow auto_fix → default deny.
 */
export function triageFinding(
  finding: Finding,
  options: PolicyOptions = {},
): TriageResult {
  const policy = loadPolicy(options.cwd ?? process.cwd());
  const sensitivePath = buildSensitivePathRegex(policy.sensitive_path_segments);
  const iacDir = buildIacDirRegex(policy.iac_dir_segments);
  const reasons: string[] = [];

  // --- suppress: not worth agent spend ---
  if (policy.noise_severities.includes(finding.severity)) {
    reasons.push(`severity=${finding.severity} treated as noise`);
    return { finding, decision: "suppress_noise", reasons };
  }

  if (options.inFlightFingerprints?.has(finding.fingerprint)) {
    reasons.push("duplicate fingerprint already remediating");
    return { finding, decision: "suppress_noise", reasons };
  }

  // --- human_only: enterprise hard stops (demo / live-extend via policy.yaml) ---
  if (policy.critical_always_human && finding.severity === "critical") {
    reasons.push("critical severity requires human authorization (policy.yaml)");
    return { finding, decision: "human_only", reasons };
  }

  if (policy.iac_always_human && finding.category === "iac") {
    reasons.push("IaC changes require human review (policy.yaml)");
    return { finding, decision: "human_only", reasons };
  }

  if (policy.secrets_always_human && finding.category === "secrets") {
    reasons.push("secret findings must not be auto-remediated (policy.yaml)");
    return { finding, decision: "human_only", reasons };
  }

  if (finding.file && sensitivePath.test(finding.file)) {
    reasons.push(`sensitive path: ${finding.file} (policy.yaml)`);
    return { finding, decision: "human_only", reasons };
  }

  if (
    finding.file &&
    (isIacFile(finding.file, policy.iac_file_extensions) ||
      iacDir.test(finding.file))
  ) {
    reasons.push(`IaC path: ${finding.file} (policy.yaml)`);
    return { finding, decision: "human_only", reasons };
  }

  if (policy.require_file_location && !finding.file) {
    reasons.push("no file location — cannot safely auto-fix");
    return { finding, decision: "human_only", reasons };
  }

  // --- auto_fix: bot-eligible work ---
  if (
    finding.category === "sca" &&
    !policy.sca_human_severities.includes(finding.severity)
  ) {
    reasons.push("dependency bump with clear package target");
    return { finding, decision: "auto_fix", reasons };
  }

  if (
    policy.sast_auto_fix_severities.includes(finding.severity) &&
    finding.startLine
  ) {
    reasons.push("SAST/code finding with file+line in non-sensitive path");
    return { finding, decision: "auto_fix", reasons };
  }

  if (finding.severity === "low") {
    reasons.push("low severity deferred for human prioritization");
    return { finding, decision: "human_only", reasons };
  }

  reasons.push("default deny — escalate to human");
  return { finding, decision: "human_only", reasons };
}

export function triageAll(
  findings: Finding[],
  options: PolicyOptions = {},
): TriageResult[] {
  reloadPolicy(options.cwd ?? process.cwd());
  return findings.map((f) => triageFinding(f, options));
}

/** Higher number = remediate sooner. Critical never reaches auto_fix. */
const SEVERITY_RANK: Record<Finding["severity"], number> = {
  critical: 60,
  high: 50,
  medium: 40,
  low: 30,
  unknown: 20,
  info: 10,
  note: 5,
};

export function severityRank(severity: Finding["severity"]): number {
  return SEVERITY_RANK[severity] ?? 0;
}

/**
 * Build the remediate queue: only auto_fix, highest severity first.
 * This is what `openfix remediate` consumes.
 */
export function prioritizeAutoFix(results: TriageResult[]): TriageResult[] {
  return results
    .filter((r) => r.decision === "auto_fix")
    .sort((a, b) => {
      const bySev =
        severityRank(b.finding.severity) - severityRank(a.finding.severity);
      if (bySev !== 0) return bySev;
      return a.finding.fingerprint.localeCompare(b.finding.fingerprint);
    });
}

export function summarizeTriage(results: TriageResult[]): Record<string, number> {
  const counts: Record<string, number> = {
    auto_fix: 0,
    human_only: 0,
    suppress_noise: 0,
  };
  for (const r of results) counts[r.decision] += 1;
  return counts;
}
