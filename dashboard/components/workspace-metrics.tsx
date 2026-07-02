"use client";

import {
  AlertTriangle,
  BarChart3,
  CalendarDays,
  GitBranch,
  LineChart,
  ListChecks,
  RadioTower,
  TimerReset,
} from "lucide-react";
import { useMemo, useState, type ReactNode } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  buildDashboardMetrics,
  failureModeCounts,
  formatPercent,
  formatSeconds,
  groupedCounts,
  latencyByAgent,
} from "@/lib/metrics";
import type { DashboardRun } from "@/lib/types";

type MetricRow = {
  label: string;
  value: string;
  share: number;
};

type TimeRange = "all" | "24h" | "7d" | "30d";

type WorkspaceMetricsProps = {
  runs: DashboardRun[];
};

const ranges: { id: TimeRange; label: string; hours: number | null }[] = [
  { id: "all", label: "All", hours: null },
  { id: "24h", label: "24h", hours: 24 },
  { id: "7d", label: "7d", hours: 24 * 7 },
  { id: "30d", label: "30d", hours: 24 * 30 },
];

export function WorkspaceMetrics({ runs }: WorkspaceMetricsProps) {
  const [timeRange, setTimeRange] = useState<TimeRange>("all");
  const filteredRuns = useMemo(() => filterRunsByRange(runs, timeRange), [runs, timeRange]);
  const metrics = useMemo(() => buildDashboardMetrics(filteredRuns), [filteredRuns]);
  const latencyRows = useMemo(() => latencyByAgent(filteredRuns), [filteredRuns]);
  const routeRows = useMemo(() => groupedCounts(filteredRuns, (run) => run.intent), [filteredRuns]);
  const statusRows = useMemo(() => groupedCounts(filteredRuns, (run) => run.status), [filteredRuns]);
  const failureRows = useMemo(() => failureModeCounts(filteredRuns), [filteredRuns]);
  const claimTotal = metrics.verifiedClaims + metrics.unverifiedClaims + metrics.contradictedClaims;
  const verificationRows: MetricRow[] = [
    {
      label: "verified",
      value: metrics.verifiedClaims.toString(),
      share: metrics.verificationRate,
    },
    {
      label: "unverified",
      value: metrics.unverifiedClaims.toString(),
      share: share(metrics.unverifiedClaims, claimTotal),
    },
    {
      label: "contradicted",
      value: metrics.contradictedClaims.toString(),
      share: share(metrics.contradictedClaims, claimTotal),
    },
  ];

  return (
    <section className="grid gap-4">
      <div className="flex flex-col gap-3 rounded-lg border border-border bg-card p-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <div className="flex items-center gap-2 text-sm font-semibold">
            <CalendarDays className="h-4 w-4 text-primary" aria-hidden="true" />
            Metrics window
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            {filteredRuns.length} runs · {formatPercent(metrics.successRate)} success · latest{" "}
            {formatSeconds(metrics.latestCompletedLatency)} · P95 completed {formatSeconds(metrics.p95Latency)}
          </p>
        </div>
        <div className="grid grid-cols-4 gap-2 sm:flex">
          {ranges.map((range) => (
            <button
              key={range.id}
              type="button"
              className={
                timeRange === range.id
                  ? "h-9 rounded-md bg-primary px-3 text-sm font-medium text-primary-foreground"
                  : "h-9 rounded-md border border-border bg-background px-3 text-sm text-muted-foreground hover:text-foreground"
              }
              onClick={() => setTimeRange(range.id)}
            >
              {range.label}
            </button>
          ))}
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
        <LatencyTrend runs={filteredRuns} />
        <BarPanel
          icon={<BarChart3 className="h-4 w-4" aria-hidden="true" />}
          title="Runs by status"
          rows={
            statusRows.length > 0
              ? statusRows.map((row) => ({
                  label: row.label,
                  value: `${row.count}`,
                  share: row.share,
                }))
              : [{ label: "none", value: "0", share: 0 }]
          }
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <MetricList
          icon={<TimerReset className="h-4 w-4" aria-hidden="true" />}
          title="Agent latency"
          rows={latencyRows.map((row) => ({
            label: row.agent,
            value: `P50 ${formatSeconds(row.p50)} / P95 ${formatSeconds(row.p95)}`,
            share: row.runCount / Math.max(1, latencyRows.reduce((total, item) => total + item.runCount, 0)),
          }))}
        />
        <MetricList
          icon={<GitBranch className="h-4 w-4" aria-hidden="true" />}
          title="Route decisions"
          rows={routeRows.map((row) => ({
            label: row.label,
            value: `${row.count} runs`,
            share: row.share,
          }))}
        />
        <BarPanel
          icon={<ListChecks className="h-4 w-4" aria-hidden="true" />}
          title="Verification labels"
          rows={verificationRows}
        />
        <MetricList
          icon={<AlertTriangle className="h-4 w-4" aria-hidden="true" />}
          title="Failure modes"
          rows={
            failureRows.length > 0
              ? failureRows.map((row) => ({
                  label: row.label,
                  value: `${row.count} hits`,
                  share: row.share,
                }))
              : [{ label: "none", value: "0 hits", share: 0 }]
          }
        />
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <RadioTower className="h-4 w-4" aria-hidden="true" />
            Routing flow
          </CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-3">
          {statusRows.length > 0 ? (
            statusRows.map((row) => (
              <div key={row.label} className="rounded-md border border-border p-3">
                <div className="flex items-center justify-between text-sm">
                  <span className="font-medium">{row.label}</span>
                  <span className="text-muted-foreground">{row.count}</span>
                </div>
                <div className="mt-3 h-2 rounded-full bg-muted">
                  <div
                    className="h-2 rounded-full bg-primary"
                    style={{ width: `${Math.max(4, row.share * 100)}%` }}
                  />
                </div>
              </div>
            ))
          ) : (
            <div className="rounded-md border border-border p-3 text-sm text-muted-foreground">No runs</div>
          )}
        </CardContent>
      </Card>
    </section>
  );
}

function LatencyTrend({ runs }: { runs: DashboardRun[] }) {
  const points = runs
    .filter((run) => run.status === "completed" && run.latency > 0)
    .slice()
    .sort((a, b) => timestamp(a.createdAt) - timestamp(b.createdAt))
    .slice(-16)
    .map((run) => ({ label: run.repoName, value: run.latency }));
  const maxValue = Math.max(1, ...points.map((point) => point.value));
  const polyline = points
    .map((point, index) => {
      const x = points.length === 1 ? 50 : (index / (points.length - 1)) * 100;
      const y = 54 - (point.value / maxValue) * 46;
      return `${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(" ");

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <LineChart className="h-4 w-4" aria-hidden="true" />
          Latency trend
        </CardTitle>
      </CardHeader>
      <CardContent className="grid gap-4">
        <div className="h-48 rounded-md border border-border bg-background p-3">
          {points.length > 0 ? (
            <svg className="h-full w-full overflow-visible" viewBox="0 0 100 60" preserveAspectRatio="none">
              <line x1="0" y1="54" x2="100" y2="54" className="stroke-border" strokeWidth="1" />
              <line x1="0" y1="8" x2="100" y2="8" className="stroke-border/60" strokeWidth="1" />
              <polyline points={polyline} fill="none" className="stroke-primary" strokeWidth="2.5" />
              {points.map((point, index) => {
                const x = points.length === 1 ? 50 : (index / (points.length - 1)) * 100;
                const y = 54 - (point.value / maxValue) * 46;
                return <circle key={`${point.label}-${index}`} cx={x} cy={y} r="1.6" className="fill-primary" />;
              })}
            </svg>
          ) : (
            <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
              No completed latency samples
            </div>
          )}
        </div>
        <div className="grid gap-2 sm:grid-cols-3">
          {points.slice(-3).map((point, index) => (
            <div key={`${point.label}-${index}`} className="rounded-md border border-border bg-muted/50 p-3">
              <div className="truncate font-mono text-xs text-muted-foreground">{point.label}</div>
              <div className="mt-1 text-lg font-semibold">{formatSeconds(point.value)}</div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function BarPanel({ icon, title, rows }: { icon: ReactNode; title: string; rows: MetricRow[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          {icon}
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {rows.map((row) => (
          <div key={row.label} className="grid gap-1.5">
            <div className="flex items-center justify-between gap-3 text-sm">
              <span className="truncate font-medium">{row.label}</span>
              <span className="shrink-0 text-muted-foreground">{row.value}</span>
            </div>
            <div className="h-7 rounded-md bg-muted">
              <div
                className={
                  row.share > 0
                    ? "flex h-7 min-w-8 items-center justify-end rounded-md bg-primary px-2 text-[11px] text-primary-foreground"
                    : "h-7 rounded-md bg-transparent"
                }
                style={{ width: `${Math.max(row.share > 0 ? 8 : 0, row.share * 100)}%` }}
              >
                {row.share > 0 ? formatPercent(row.share) : ""}
              </div>
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

function MetricList({ icon, title, rows }: { icon: ReactNode; title: string; rows: MetricRow[] }) {
  const normalizedRows = rows.length > 0 ? rows : [{ label: "none", value: "0", share: 0 }];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          {icon}
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {normalizedRows.map((row) => (
          <div key={row.label} className="space-y-1.5">
            <div className="flex items-center justify-between gap-3 text-sm">
              <span className="truncate font-medium">{row.label}</span>
              <span className="shrink-0 text-muted-foreground">{row.value}</span>
            </div>
            <div className="h-2 rounded-full bg-muted">
              <div
                className="h-2 rounded-full bg-primary"
                style={{ width: `${Math.max(row.share > 0 ? 4 : 0, row.share * 100)}%` }}
              />
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

function filterRunsByRange(runs: DashboardRun[], timeRange: TimeRange) {
  const range = ranges.find((item) => item.id === timeRange);
  if (!range?.hours) {
    return runs;
  }

  const cutoff = Date.now() - range.hours * 60 * 60 * 1000;
  return runs.filter((run) => timestamp(run.createdAt) >= cutoff);
}

function share(value: number, total: number) {
  return total === 0 ? 0 : value / total;
}

function timestamp(value: string): number {
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : 0;
}
