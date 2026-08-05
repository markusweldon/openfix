/**
 * OpenFix types — the shared data model for the whole pipeline.
 *
 * Interview talking point:
 *   Scanner output (any vendor) → Finding → Policy Decision → Agent PR
 * Everything downstream speaks "Finding", never raw Semgrep/Snyk/OSV shapes.
 */
import { z } from "zod";

/** Normalized severity so Semgrep "error" and OSV "7.2" become comparable. */
export const SeveritySchema = z.enum([
  "critical",
  "high",
  "medium",
  "low",
  "info",
  "note",
  "unknown",
]);

export type Severity = z.infer<typeof SeveritySchema>;

/**
 * One security finding after ingest.
 * `fingerprint` dedupes remediations (same issue shouldn't spawn two agents).
 * `category` drives policy (e.g. secrets → human_only).
 */
export const FindingSchema = z.object({
  id: z.string(),
  tool: z.string(), // e.g. "semgrep", "osv-scanner" — scanner that detected it
  ruleId: z.string(), // vendor rule / CVE id
  severity: SeveritySchema,
  title: z.string(),
  message: z.string(),
  file: z.string().optional(),
  startLine: z.number().int().positive().optional(),
  endLine: z.number().int().positive().optional(),
  fingerprint: z.string(),
  category: z.enum(["sast", "sca", "secrets", "iac", "other"]).default("other"),
  raw: z.unknown().optional(), // original SARIF result kept for audit / debug
});

export type Finding = z.infer<typeof FindingSchema>;

/** Optional native JSON format if a tool doesn't emit SARIF. */
export const FindingsFileSchema = z.object({
  version: z.literal(1),
  source: z.string().optional(),
  findings: z.array(FindingSchema),
});

export type FindingsFile = z.infer<typeof FindingsFileSchema>;

/**
 * Policy outcomes — THIS is the enterprise control plane.
 * - auto_fix: Cursor agent may open a remediation PR
 * - human_only: do NOT call the agent (secrets/critical/auth/etc.)
 * - suppress_noise: drop info/style/duplicates
 */
export const DecisionSchema = z.enum([
  "auto_fix",
  "human_only",
  "suppress_noise",
]);

export type Decision = z.infer<typeof DecisionSchema>;

export const TriageResultSchema = z.object({
  finding: FindingSchema,
  decision: DecisionSchema,
  reasons: z.array(z.string()), // human-readable why — great for the demo
});

export type TriageResult = z.infer<typeof TriageResultSchema>;
