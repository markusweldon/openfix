/**
 * CLI presentation helpers — finding-lane board, fleet summary, stream labels.
 */
import type { Finding } from "../types/finding.js";

/** Parse agent ids from pasted status lines (bc-… / agent=bc-…). */
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

/** Short finding slug from ruleId (last path segment, truncated). */
export function findingSlug(ruleId: string, maxLen = 20): string {
  const parts = ruleId.split(/[/.:]/).filter(Boolean);
  let slug = parts[parts.length - 1] ?? ruleId;
  // Prefer a readable trailing segment for long Semgrep ids
  if (slug.length < 4 && parts.length >= 2) {
    slug = parts.slice(-2).join("-");
  }
  // Common Semgrep: …path-join-resolve-traversal → path-traversal-ish last bits
  if (ruleId.includes("path-traversal") || ruleId.includes("path-join")) {
    slug = "path-traversal";
  } else if (ruleId.includes("sql-injection") || ruleId.includes("sqli")) {
    slug = "sqli";
  } else if (ruleId.includes("command-injection") || ruleId.includes("cmdi")) {
    slug = "cmdi";
  } else if (ruleId.includes("open-redirect")) {
    slug = "open-redirect";
  } else if (ruleId.includes("ssrf")) {
    slug = "ssrf";
  } else if (ruleId.includes("xss")) {
    slug = ruleId.includes("html") ? "xss-html" : "xss";
  } else if (ruleId.includes("cors")) {
    slug = "cors";
  } else if (ruleId.includes("weak-crypto") || ruleId.includes("createcipher")) {
    slug = "weak-crypto";
  } else if (ruleId.includes("vm-runinnewcontext") || ruleId.includes("sandbox")) {
    slug = "vm-sandbox";
  } else if (ruleId.includes("object-assign") || ruleId.includes("config-merge")) {
    slug = "config-merge";
  } else if (ruleId.includes("execfile") || ruleId.includes("shell-true")) {
    slug = "execfile-shell";
  } else if (/^CVE-\d/i.test(slug) || /^CVE-\d/i.test(ruleId)) {
    const cve = ruleId.match(/CVE-\d{4}-\d+/i)?.[0] ?? slug;
    slug = cve;
  }
  if (slug.length > maxLen) slug = slug.slice(0, maxLen - 1) + "…";
  return slug;
}

/** file:line for board LOCATION column. */
export function findingLocation(finding: Finding): string {
  const file = finding.file ?? "?";
  return finding.startLine ? `${file}:${finding.startLine}` : file;
}

/** Disambiguate duplicate slugs in a batch (path-traversal, path-traversal~2). */
export function uniqueFindingSlugs(findings: Finding[]): string[] {
  const counts = new Map<string, number>();
  const base = findings.map((f) => findingSlug(f.ruleId));
  for (const s of base) counts.set(s, (counts.get(s) ?? 0) + 1);
  const seen = new Map<string, number>();
  return base.map((s) => {
    if ((counts.get(s) ?? 0) <= 1) return s;
    const n = (seen.get(s) ?? 0) + 1;
    seen.set(s, n);
    return n === 1 ? s : `${s}~${n}`;
  });
}

export type LanePhase =
  | "starting"
  | "running"
  | "opening_pr"
  | "finished"
  | "error"
  | "cancelled";

const SPINNER = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"] as const;
const IN_PROGRESS: ReadonlySet<LanePhase> = new Set([
  "starting",
  "running",
  "opening_pr",
]);

const COL = { sev: 8, finding: 20, location: 24 } as const;

export interface LaneSpec {
  id: string;
  severity: string;
  finding: string;
  location: string;
}

interface LaneState extends LaneSpec {
  phase: LanePhase;
  detail?: string;
  prUrl?: string;
}

function pad(s: string, w: number): string {
  const t = s.length > w ? s.slice(0, w - 1) + "…" : s;
  return t.padEnd(w);
}

function prShort(url?: string): string {
  if (!url) return "";
  const m = url.match(/\/pull\/(\d+)/);
  return m ? `PR #${m[1]}` : url;
}

function phaseLabel(lane: LaneState, frame: number): string {
  const { phase, detail, prUrl } = lane;
  if (IN_PROGRESS.has(phase)) {
    const spin = SPINNER[frame % SPINNER.length]!;
    const text =
      phase === "starting"
        ? "starting"
        : phase === "opening_pr"
          ? "opening PR…"
          : detail?.trim()
            ? truncateStatus(detail, 28)
            : "running";
    return `${spin} ${text}`;
  }
  if (phase === "finished") {
    const pr = prShort(prUrl);
    return pr ? `✓ finished  ${pr}` : "✓ finished";
  }
  if (phase === "error") {
    return detail ? `✗ error  ${truncateStatus(detail, 24)}` : "✗ error";
  }
  return "– cancelled";
}

function truncateStatus(s: string, max: number): string {
  const one = s.replace(/\s+/g, " ").trim();
  return one.length > max ? one.slice(0, max - 1) + "…" : one;
}

function formatLaneRow(lane: LaneState, frame: number): string {
  return (
    `  ${pad(lane.severity, COL.sev)}` +
    `${pad(lane.finding, COL.finding)}` +
    `${pad(lane.location, COL.location)}` +
    `${phaseLabel(lane, frame)}`
  );
}

/**
 * Live finding-lane board: in-place ANSI updates on TTY; append on non-TTY.
 * STATUS uses fixed labels (starting / opening PR / finished) or a short
 * assistant-stream hint while running — not the full transcript (--verbose).
 */
export class LaneBoard {
  private readonly lanes: LaneState[];
  private readonly remainingQueued: number;
  private readonly tty: boolean;
  private frame = 0;
  private timer: ReturnType<typeof setInterval> | null = null;
  private painted = false;
  private stopped = false;

  constructor(specs: LaneSpec[], remainingQueued = 0) {
    this.lanes = specs.map((s) => ({
      ...s,
      phase: "starting" as LanePhase,
    }));
    this.remainingQueued = remainingQueued;
    this.tty = Boolean(process.stdout.isTTY);
  }

  get height(): number {
    // header + rows + optional queued footer
    return 1 + this.lanes.length + (this.remainingQueued > 0 ? 1 : 0);
  }

  /** Initial paint + start spinner (TTY). */
  start(): void {
    if (this.tty) {
      process.stdout.write("\x1b[?25l"); // hide cursor
    }
    this.paint(true);
    this.painted = true;
    if (this.tty) {
      this.timer = setInterval(() => {
        if (this.stopped) return;
        if (!this.lanes.some((l) => IN_PROGRESS.has(l.phase))) return;
        this.frame += 1;
        this.repaint();
      }, 80);
    }
  }

  setPhase(
    id: string,
    phase: LanePhase,
    opts?: { detail?: string; prUrl?: string },
  ): void {
    const lane = this.lanes.find((l) => l.id === id);
    if (!lane) return;
    lane.phase = phase;
    if (opts?.detail !== undefined) lane.detail = opts.detail;
    if (opts?.prUrl !== undefined) lane.prUrl = opts.prUrl;

    if (!this.tty) {
      console.log(formatLaneRow(lane, 0));
      return;
    }
    if (!this.painted) {
      this.start();
      return;
    }
    this.repaint();
  }

  /** Stop spinner, final paint, show cursor. */
  finish(): void {
    this.stopped = true;
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
    if (this.tty && this.painted) {
      this.repaint();
      process.stdout.write("\x1b[?25h"); // show cursor
      process.stdout.write("\n");
    }
  }

  private headerLine(): string {
    return (
      `  ${pad("SEV", COL.sev)}` +
      `${pad("FINDING", COL.finding)}` +
      `${pad("LOCATION", COL.location)}` +
      `STATUS`
    );
  }

  private queuedLine(): string | null {
    if (this.remainingQueued <= 0) return null;
    return `  … ${this.remainingQueued} more queued (severity-ordered)`;
  }

  private allLines(): string[] {
    const lines = [this.headerLine(), ...this.lanes.map((l) => formatLaneRow(l, this.frame))];
    const q = this.queuedLine();
    if (q) lines.push(q);
    return lines;
  }

  private paint(initial: boolean): void {
    const lines = this.allLines();
    if (initial || !this.tty) {
      for (const line of lines) console.log(line);
      return;
    }
    this.repaint();
  }

  private repaint(): void {
    if (!this.tty) return;
    const lines = this.allLines();
    const h = lines.length;
    // Move to start of board, rewrite each line
    process.stdout.write(`\x1b[${h}A`);
    for (const line of lines) {
      process.stdout.write(`\x1b[2K\r${line}\n`);
    }
  }
}

/** Copy-paste next steps after a live remediate (single-agent). */
export function printNextSteps(agentId: string, prUrl?: string): void {
  printFleetNextSteps(
    [{ agentId, prUrl }],
  );
}

/** Fleet-aware next steps — every agent/PR from the batch (not only --last). */
export function printFleetNextSteps(
  rows: Array<{ agentId?: string; prUrl?: string }>,
): void {
  const prs = rows.map((r) => r.prUrl).filter((u): u is string => Boolean(u));
  const agents = rows
    .map((r) => r.agentId)
    .filter((id): id is string => Boolean(id) && id !== "unknown");
  // Dedupe while preserving order (concurrent fleet may list unique bc- ids)
  const uniqueAgents = [...new Set(agents)];
  const lastAgent = [...uniqueAgents].reverse()[0];

  console.log("\n── Next ──");
  if (prs.length === 0) {
    console.log("  npx tsx src/cli.ts verify");
  } else {
    for (const pr of prs) {
      console.log(`  npx tsx src/cli.ts verify --pr ${pr}`);
    }
  }
  for (const id of uniqueAgents) {
    console.log(`  npx tsx src/cli.ts status ${id}`);
    console.log(
      `  npx tsx src/cli.ts resume ${id} --prompt "Address review feedback: strengthen the regression test."`,
    );
  }
  if (lastAgent) {
    console.log("  npx tsx src/cli.ts status --last");
    console.log(
      `  npx tsx src/cli.ts resume --last --prompt "Address review feedback: strengthen the regression test."`,
    );
  }
  console.log("");
}

export interface FleetRow {
  /** Finding slug (lane identity). */
  label: string;
  fingerprint: string;
  ruleId: string;
  status: string;
  agentId?: string;
  prUrl?: string;
  error?: string;
}

/** End-of-run table for concurrent / board remediate (includes bc-… for resume). */
export function printFleetSummary(
  rows: FleetRow[],
  remainingQueued = 0,
): void {
  console.log("\n── Fleet ──");
  for (const row of rows) {
    const agent =
      row.agentId && row.agentId !== "unknown" ? row.agentId : "—";
    const pr = row.prUrl ?? "—";
    console.log(
      `  ${row.label.padEnd(18)} ${row.status.padEnd(10)} ${agent.padEnd(28)} ${pr}`,
    );
    if (row.error) console.log(`       error=${row.error}`);
  }
  const ok = rows.filter((r) => r.status === "finished").length;
  const err = rows.filter((r) => r.status === "error").length;
  const other = rows.length - ok - err;
  const queued =
    remainingQueued > 0 ? ` · ${remainingQueued} still queued` : "";
  console.log(
    `  ${ok} finished · ${err} error · ${other} other${queued}`,
  );
}

/**
 * Line-buffered stdout writer with a finding-slug label (--verbose).
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
