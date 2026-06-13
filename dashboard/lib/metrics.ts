import type {
  ApiRunError,
  ApiRunSummary,
  DashboardMetrics,
  DashboardRun,
  RunError,
  RunIntent,
  TraceMetadataValue,
} from "@/lib/types";

export function toDashboardRun(run: ApiRunSummary): DashboardRun {
  const traceMetadata = run.trace_metadata ?? {};
  const agentName = stringValue(traceMetadata.agent_name) ?? "supervisor";
  const latency = numberValue(traceMetadata.latency);
  const tokens = numberValue(traceMetadata.tokens);
  const costUsd = numberValue(traceMetadata.cost_usd);
  const errors = run.errors.map(toRunError);

  return {
    jobId: run.job_id,
    userId: run.user_id,
    repoName: repoNameFromUrl(run.repo_url),
    repoUrl: run.repo_url,
    query: run.query,
    intent: intentFromQuery(run.query),
    status: run.status,
    currentNode: run.current_node,
    finalOutput: run.final_output,
    error: run.error,
    partialSummaries: run.partial_summaries,
    errors,
    userCorrections: run.user_corrections,
    verifiedCount: run.verified_count,
    unverifiedCount: run.unverified_count,
    contradictedCount: run.contradicted_count,
    claimProvenance: (run.claim_provenance ?? []).map((row) => ({
      agent: row.agent,
      claimsMade: row.claims_made,
      verified: row.verified,
      unverified: row.unverified,
      contradicted: row.contradicted,
      summary: row.summary,
    })),
    traceUrl: run.trace_url,
    traceMetadata,
    agentName,
    toolName: stringValue(traceMetadata.tool_name),
    mcpServer: stringValue(traceMetadata.mcp_server),
    latency,
    tokens,
    costUsd,
    failureModes: failureModesFromErrors(errors, run.contradicted_count),
    createdAt: run.created_at,
    updatedAt: run.updated_at,
  };
}

export function buildDashboardMetrics(runs: DashboardRun[]): DashboardMetrics {
  const activeRuns = runs.filter((run) => run.status === "queued" || run.status === "running").length;
  const completedRuns = runs.filter((run) => run.status === "completed").length;
  const failedRuns = runs.filter((run) => run.status === "failed").length;
  const terminalRuns = completedRuns + failedRuns;
  const completedLatencyRuns = runs.filter((run) => run.status === "completed" && run.latency > 0);
  const completedLatencies = completedLatencyRuns.map((run) => run.latency);
  const verifiedClaims = sum(runs, (run) => run.verifiedCount);
  const unverifiedClaims = sum(runs, (run) => run.unverifiedCount);
  const contradictedClaims = sum(runs, (run) => run.contradictedCount);
  const denominator = verifiedClaims + unverifiedClaims + contradictedClaims;

  return {
    totalRuns: runs.length,
    activeRuns,
    completedRuns,
    failedRuns,
    terminalRuns,
    successRate: terminalRuns === 0 ? 0 : completedRuns / terminalRuns,
    verifiedClaims,
    unverifiedClaims,
    contradictedClaims,
    verificationRate: denominator === 0 ? 0 : verifiedClaims / denominator,
    latestCompletedLatency: latestCompletedLatency(completedLatencyRuns),
    completedLatencySamples: completedLatencyRuns.length,
    p50Latency: percentile(completedLatencies, 50),
    p95Latency: percentile(completedLatencies, 95),
    totalTokens: sum(runs, (run) => run.tokens),
    totalCostUsd: sum(runs, (run) => run.costUsd),
  };
}

export function groupedCounts(
  runs: DashboardRun[],
  keyForRun: (run: DashboardRun) => string,
): { label: string; count: number; share: number }[] {
  const counts = new Map<string, number>();
  for (const run of runs) {
    const key = keyForRun(run);
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }

  return [...counts.entries()]
    .sort((a, b) => b[1] - a[1])
    .map(([label, count]) => ({
      label,
      count,
      share: runs.length === 0 ? 0 : count / runs.length,
    }));
}

export function latencyByAgent(
  runs: DashboardRun[],
): { agent: string; p50: number; p95: number; runCount: number }[] {
  const grouped = new Map<string, number[]>();
  for (const run of runs) {
    if (run.status !== "completed" || run.latency <= 0) {
      continue;
    }
    const latencies = grouped.get(run.agentName) ?? [];
    latencies.push(run.latency);
    grouped.set(run.agentName, latencies);
  }

  return [...grouped.entries()].map(([agent, latencies]) => ({
    agent,
    p50: percentile(latencies, 50),
    p95: percentile(latencies, 95),
    runCount: latencies.length,
  }));
}

export function failureModeCounts(
  runs: DashboardRun[],
): { label: string; count: number; share: number }[] {
  const modes = new Map<string, number>();
  let total = 0;
  for (const run of runs) {
    for (const mode of run.failureModes) {
      modes.set(mode, (modes.get(mode) ?? 0) + 1);
      total += 1;
    }
  }

  return [...modes.entries()]
    .sort((a, b) => b[1] - a[1])
    .map(([label, count]) => ({ label, count, share: total === 0 ? 0 : count / total }));
}

export function formatPercent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

export function formatSeconds(value: number): string {
  return `${value.toFixed(1)}s`;
}

export function formatCurrency(value: number): string {
  return `$${value.toFixed(3)}`;
}

function toRunError(error: ApiRunError): RunError {
  return {
    node: error.node,
    errorType: error.error_type,
    message: error.message,
    retryable: error.retryable,
  };
}

function repoNameFromUrl(repoUrl: string): string {
  if (repoUrl.startsWith("local://")) {
    return repoUrl.replace("local://", "");
  }

  try {
    const url = new URL(repoUrl);
    const parts = url.pathname.split("/").filter(Boolean);
    return parts.slice(-2).join("/") || repoUrl;
  } catch {
    return repoUrl.split("/").filter(Boolean).slice(-2).join("/") || repoUrl;
  }
}

function intentFromQuery(query: string): RunIntent {
  const lowered = query.toLowerCase();
  if (lowered.includes("architecture") || lowered.includes("structure") || lowered.includes("map")) {
    return "architectural";
  }
  if (lowered.includes("runtime") || lowered.includes("run") || lowered.includes("entry")) {
    return "runtime";
  }
  if (lowered.includes("behavior") || lowered.includes("flow") || lowered.includes("function")) {
    return "behavioral";
  }
  if (lowered.includes("debug") || lowered.includes("error") || lowered.includes("failing")) {
    return "debug";
  }
  return "mixed";
}

function failureModesFromErrors(errors: RunError[], contradictedCount: number): string[] {
  const modes = errors.map((error) => error.errorType);
  if (contradictedCount > 0) {
    modes.push("contradicted_claim");
  }
  return modes;
}

function stringValue(value: TraceMetadataValue | undefined): string | null {
  return typeof value === "string" && value.length > 0 ? value : null;
}

function numberValue(value: TraceMetadataValue | undefined): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

function sum(runs: DashboardRun[], valueForRun: (run: DashboardRun) => number): number {
  return runs.reduce((total, run) => total + valueForRun(run), 0);
}

function latestCompletedLatency(runs: DashboardRun[]): number {
  let latestRun: DashboardRun | null = null;
  for (const run of runs) {
    if (latestRun === null || timestamp(run.updatedAt) > timestamp(latestRun.updatedAt)) {
      latestRun = run;
    }
  }
  return latestRun?.latency ?? 0;
}

function timestamp(value: string): number {
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function percentile(values: number[], target: number): number {
  const sorted = values.filter((value) => Number.isFinite(value)).sort((a, b) => a - b);
  if (sorted.length === 0) {
    return 0;
  }

  const rank = Math.ceil((target / 100) * sorted.length) - 1;
  return sorted[Math.max(0, Math.min(sorted.length - 1, rank))];
}
