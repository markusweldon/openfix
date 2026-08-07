/**
 * Simulated scanner adapters — produce the same Finding[] as SARIF ingest.
 *
 * Enterprise path remains SARIF/JSON from CI. These adapters show a second
 * ingest door (e.g. future Semgrep/Snyk MCP) without replacing the pipeline contract.
 */
import type { Finding } from "../types/finding.js";

export type SimulatedScanner = "semgrep" | "snyk";

/**
 * Return a small fixed finding set as if an MCP scanner client returned results.
 * Not a live MCP call — prototype / demo only.
 */
export function loadSimulatedMcpFindings(
  scanner: SimulatedScanner,
): Finding[] {
  if (scanner === "snyk") {
    return [
      {
        id: "simulated-snyk-lodash",
        tool: "snyk",
        ruleId: "SNYK-JS-LODASH-567746",
        severity: "high",
        title: "Prototype Pollution in lodash",
        message:
          "Simulated Snyk MCP finding: lodash < 4.17.21 allows prototype pollution.",
        file: "package.json",
        startLine: 12,
        fingerprint: "simulated-snyk-lodash-567746",
        category: "sca",
        raw: { adapter: "simulated:mcp:snyk" },
      },
      {
        id: "simulated-snyk-axios",
        tool: "snyk",
        ruleId: "SNYK-JS-AXIOS-1579269",
        severity: "medium",
        title: "Server-Side Request Forgery in axios",
        message:
          "Simulated Snyk MCP finding: axios follows redirects to attacker-controlled URLs.",
        file: "package.json",
        startLine: 10,
        fingerprint: "simulated-snyk-axios-1579269",
        category: "sca",
        raw: { adapter: "simulated:mcp:snyk" },
      },
    ];
  }

  // default: semgrep
  return [
    {
      id: "simulated-semgrep-path-traversal",
      tool: "semgrep",
      ruleId:
        "javascript.lang.security.audit.path-traversal.path-join-resolve-traversal",
      severity: "high",
      title: "Path traversal via path.join",
      message:
        "Simulated Semgrep MCP finding: user-controlled path reaches path.join without a jail.",
      file: "src/files.js",
      startLine: 8,
      fingerprint: "simulated-semgrep-path-traversal-001",
      category: "sast",
      raw: { adapter: "simulated:mcp:semgrep" },
    },
    {
      id: "simulated-semgrep-sqli",
      tool: "semgrep",
      ruleId: "javascript.lang.security.audit.sql-injection-string-concat",
      severity: "high",
      title: "SQL injection via string concat",
      message:
        "Simulated Semgrep MCP finding: user input concatenated into SQL.",
      file: "src/db/query.js",
      startLine: 4,
      fingerprint: "simulated-semgrep-sqli-001",
      category: "sast",
      raw: { adapter: "simulated:mcp:semgrep" },
    },
    {
      id: "simulated-semgrep-xss",
      tool: "semgrep",
      ruleId: "javascript.lang.security.audit.xss.direct-response-write",
      severity: "medium",
      title: "Reflected XSS via response write",
      message:
        "Simulated Semgrep MCP finding: unescaped user input written to the response.",
      file: "src/server.js",
      startLine: 29,
      fingerprint: "simulated-semgrep-xss-001",
      category: "sast",
      raw: { adapter: "simulated:mcp:semgrep" },
    },
  ];
}

export function parseSimulatedFromSpec(
  spec: string,
): SimulatedScanner | undefined {
  // Accept: simulated:semgrep | mcp:semgrep | simulated:mcp:snyk
  const m = spec
    .trim()
    .toLowerCase()
    .match(/^(?:simulated:)?(?:mcp:)?(semgrep|snyk)$/);
  return m ? (m[1] as SimulatedScanner) : undefined;
}
