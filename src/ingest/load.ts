/**
 * Ingest — turn scanner output into OpenFix Findings.
 *
 * Supports:
 *   1) SARIF 2.x (industry interchange — Semgrep, CodeQL, many SCA tools)
 *   2) OpenFix findings JSON (version: 1) for anything that isn't SARIF
 *
 * Interview talking point:
 *   "SARIF = Static Analysis Results Interchange Format. We're scanner-agnostic:
 *    we don't call Snyk's API; we consume the format enterprises already emit in CI."
 */
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { z } from "zod";
import {
  FindingSchema,
  FindingsFileSchema,
  type Finding,
  type Severity,
} from "../types/finding.js";

/** Map SARIF level strings → our severity enum when no numeric score exists. */
const SarifLevelToSeverity: Record<string, Severity> = {
  error: "high",
  warning: "medium",
  note: "info",
  none: "note",
};

/** Loose SARIF shape — enough fields to build Findings; ignore vendor extras. */
const SarifSchema = z.object({
  version: z.string().optional(),
  runs: z.array(
    z.object({
      tool: z
        .object({
          driver: z
            .object({
              name: z.string().optional(),
              rules: z
                .array(
                  z.object({
                    id: z.string(),
                    name: z.string().optional(),
                    shortDescription: z
                      .object({ text: z.string().optional() })
                      .optional(),
                    fullDescription: z
                      .object({ text: z.string().optional() })
                      .optional(),
                    defaultConfiguration: z
                      .object({ level: z.string().optional() })
                      .optional(),
                    properties: z
                      .object({
                        security_severity: z.string().optional(),
                        tags: z.array(z.string()).optional(),
                      })
                      .passthrough()
                      .optional(),
                  }),
                )
                .optional(),
            })
            .passthrough(),
        })
        .passthrough(),
      results: z
        .array(
          z.object({
            ruleId: z.string().optional(),
            level: z.string().optional(),
            message: z.object({ text: z.string().optional() }).optional(),
            fingerprints: z.record(z.string(), z.string()).optional(),
            partialFingerprints: z.record(z.string(), z.string()).optional(),
            locations: z
              .array(
                z.object({
                  physicalLocation: z
                    .object({
                      artifactLocation: z
                        .object({ uri: z.string().optional() })
                        .optional(),
                      region: z
                        .object({
                          startLine: z.number().optional(),
                          endLine: z.number().optional(),
                        })
                        .optional(),
                    })
                    .optional(),
                }),
              )
              .optional(),
            properties: z.record(z.string(), z.unknown()).optional(),
          }),
        )
        .optional(),
    }),
  ),
});

function fingerprintOf(parts: string[]): string {
  return createHash("sha256").update(parts.join("|")).digest("hex").slice(0, 16);
}

/** Prefer numeric security_severity (CVSS-like) when scanners provide it. */
function normalizeSeverity(
  level: string | undefined,
  securitySeverity: string | undefined,
): Severity {
  if (securitySeverity) {
    const n = Number.parseFloat(securitySeverity);
    if (!Number.isNaN(n)) {
      if (n >= 9) return "critical";
      if (n >= 7) return "high";
      if (n >= 4) return "medium";
      if (n >= 1) return "low";
      return "info";
    }
    const s = securitySeverity.toLowerCase();
    if (s === "critical" || s === "high" || s === "medium" || s === "low") {
      return s;
    }
  }
  if (!level) return "unknown";
  return SarifLevelToSeverity[level.toLowerCase()] ?? "unknown";
}

/** Heuristic category from tags/rule text — feeds policy (secrets vs sca vs sast). */
function inferCategory(
  tags: string[] | undefined,
  ruleId: string,
  message: string,
): Finding["category"] {
  const blob = `${(tags ?? []).join(" ")} ${ruleId} ${message}`.toLowerCase();
  if (/\b(sca|dependency|cve-|ghsa-|npm|package)\b/.test(blob)) return "sca";
  if (/\b(secret|credential|api[_-]?key|password|token)\b/.test(blob))
    return "secrets";
  if (/\b(iac|terraform|cloudformation|dockerfile|kubernetes)\b/.test(blob))
    return "iac";
  if (/\b(sast|injection|xss|path.?traversal|sqli)\b/.test(blob)) return "sast";
  return "other";
}

/** SARIF runs[] → Finding[]. Multiple tools can appear as multiple runs in one file. */
export function normalizeSarif(raw: unknown): Finding[] {
  const sarif = SarifSchema.parse(raw);
  const findings: Finding[] = [];

  for (const run of sarif.runs) {
    const tool = run.tool.driver.name ?? "unknown-scanner";
    const rules = new Map(
      (run.tool.driver.rules ?? []).map((r) => [r.id, r] as const),
    );

    for (const result of run.results ?? []) {
      const ruleId = result.ruleId ?? "unknown-rule";
      const rule = rules.get(ruleId);
      const loc = result.locations?.[0]?.physicalLocation;
      const file = loc?.artifactLocation?.uri;
      const startLine = loc?.region?.startLine;
      const endLine = loc?.region?.endLine;
      const message =
        result.message?.text ??
        rule?.shortDescription?.text ??
        rule?.fullDescription?.text ??
        ruleId;
      const title =
        rule?.shortDescription?.text ?? rule?.name ?? `${tool}:${ruleId}`;
      const severity = normalizeSeverity(
        result.level ?? rule?.defaultConfiguration?.level,
        rule?.properties?.security_severity,
      );
      // Prefer scanner fingerprint; otherwise hash key fields ourselves.
      const fp =
        result.fingerprints?.["primaryLocationLineHash"] ??
        result.partialFingerprints?.["primaryLocationLineHash"] ??
        fingerprintOf([tool, ruleId, file ?? "", String(startLine ?? ""), message]);

      const finding = FindingSchema.parse({
        id: `${tool}:${fp}`,
        tool,
        ruleId,
        severity,
        title,
        message,
        file,
        startLine,
        endLine,
        fingerprint: fp,
        category: inferCategory(rule?.properties?.tags, ruleId, message),
        raw: result,
      });
      findings.push(finding);
    }
  }

  return findings;
}

export function normalizeFindingsJson(raw: unknown): Finding[] {
  const parsed = FindingsFileSchema.parse(raw);
  return parsed.findings;
}

/** Entry point used by `openfix ingest <path>`. */
export async function loadFindings(path: string): Promise<Finding[]> {
  const text = await readFile(path, "utf8");
  const raw: unknown = JSON.parse(text);

  // SARIF documents always have a top-level `runs` array.
  if (
    raw &&
    typeof raw === "object" &&
    "runs" in raw &&
    Array.isArray((raw as { runs: unknown }).runs)
  ) {
    return normalizeSarif(raw);
  }

  if (
    raw &&
    typeof raw === "object" &&
    "findings" in raw &&
    Array.isArray((raw as { findings: unknown }).findings)
  ) {
    return normalizeFindingsJson(raw);
  }

  throw new Error(
    `Unrecognized findings format in ${path}. Expected SARIF 2.x or OpenFix findings JSON (version: 1).`,
  );
}
