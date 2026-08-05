/**
 * Parse agent ids from messy demo paste.
 * Accepts: bc-… | agent=bc-… | "agent=bc-… run=run-…"
 */
export function parseAgentId(raw: string): string {
  const text = raw.trim();
  const fromLabel = text.match(/(?:^|\s)agent=([^\s]+)/i);
  if (fromLabel?.[1]) return stripAgentPrefix(fromLabel[1]);

  const bc = text.match(/\b(bc-[a-z0-9-]+)\b/i);
  if (bc?.[1]) return bc[1];

  return stripAgentPrefix(text.split(/\s+/)[0] ?? text);
}

function stripAgentPrefix(value: string): string {
  return value.replace(/^agent=/i, "").trim();
}

/** Copy-paste next steps after a live remediate. */
export function printNextSteps(agentId: string, prUrl?: string): void {
  console.log(`
── Next (async / multi-step) ──
npx tsx src/cli.ts status --last
npx tsx src/cli.ts status ${agentId}
npx tsx src/cli.ts resume --last --prompt "Address review feedback: strengthen the regression test."
npx tsx src/cli.ts resume ${agentId} --prompt "Address review feedback: strengthen the regression test."
${prUrl ? `npx tsx src/cli.ts verify --pr ${prUrl}\nOpen PR: ${prUrl}` : "npx tsx src/cli.ts verify"}
`);
}

/**
 * Line-buffered stdout writer with a per-agent label for concurrent remediations.
 * Partial chunks stay buffered until newline so multiplexed streams stay readable.
 */
export function createLabeledStreamWriter(label: string): {
  write: (chunk: string) => void;
  flush: () => void;
} {
  let buf = "";
  const prefix = `[${label}] `;
  return {
    write(chunk: string) {
      buf += chunk;
      let nl = buf.indexOf("\n");
      while (nl >= 0) {
        process.stdout.write(prefix + buf.slice(0, nl + 1));
        buf = buf.slice(nl + 1);
        nl = buf.indexOf("\n");
      }
    },
    flush() {
      if (buf.length > 0) {
        process.stdout.write(prefix + buf + "\n");
        buf = "";
      }
    },
  };
}

export interface FleetRow {
  label: string;
  fingerprint: string;
  ruleId: string;
  status: string;
  agentId?: string;
  prUrl?: string;
  error?: string;
}

/** End-of-run table for concurrent remediate. */
export function printFleetSummary(rows: FleetRow[]): void {
  console.log("\n── Fleet summary ──");
  for (const row of rows) {
    const id = row.agentId && row.agentId !== "unknown" ? row.agentId : "—";
    const pr = row.prUrl ?? "—";
    console.log(
      `  ${row.label.padEnd(4)} ${row.status.padEnd(10)} ${row.ruleId}`,
    );
    console.log(`       fp=${row.fingerprint}  agent=${id}`);
    console.log(`       pr=${pr}`);
    if (row.error) console.log(`       error=${row.error}`);
  }
  const ok = rows.filter((r) => r.status === "finished").length;
  const err = rows.filter((r) => r.status === "error").length;
  console.log(
    `\n  ${rows.length} agent(s): ${ok} finished, ${err} error, ${rows.length - ok - err} other`,
  );
  console.log(
    "  Org scale = same OpenFix lane in each app's CI (one SARIF/repo), not one mega-router.",
  );
}
