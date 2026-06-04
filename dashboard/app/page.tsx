import {
  Activity,
  AlertTriangle,
  CircleDollarSign,
  GitBranch,
  ListChecks,
  RadioTower,
  ShieldCheck,
  TimerReset,
} from "lucide-react";

import { RunStatusTable } from "@/components/run-status-table";
import { StatCard } from "@/components/stat-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getDashboardData } from "@/lib/api";
import {
  buildDashboardMetrics,
  failureModeCounts,
  formatCurrency,
  formatPercent,
  formatSeconds,
  groupedCounts,
  latencyByAgent,
} from "@/lib/metrics";

export default async function DashboardPage() {
  const { runs, source, apiBaseUrl } = await getDashboardData();
  const latest = runs[0];
  const metrics = buildDashboardMetrics(runs);
  const routeRows = groupedCounts(runs, (run) => run.intent);
  const statusRows = groupedCounts(runs, (run) => run.status);
  const latencyRows = latencyByAgent(runs);
  const failureRows = failureModeCounts(runs);

  return (
    <main className="min-h-screen bg-muted px-6 py-6">
      <div className="mx-auto flex max-w-7xl flex-col gap-6">
        <header className="flex flex-col gap-4 border-b border-border pb-5 md:flex-row md:items-end md:justify-between">
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <Badge variant="success">Commit 8 dashboard</Badge>
              <Badge variant={source === "api" ? "success" : "warning"}>
                {source === "api" ? "Live API" : "Demo data"}
              </Badge>
            </div>
            <div>
              <h1 className="text-3xl font-semibold tracking-normal">wayfinder runs</h1>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
                Monitor codebase onboarding runs, verification status, traces, latency, cost, routing
                decisions, and resilience failure modes.
              </p>
              <p className="mt-1 text-xs text-muted-foreground">API: {apiBaseUrl}</p>
            </div>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" asChild>
              <a href={latest?.traceUrl ?? "https://smith.langchain.com/"}>View traces</a>
            </Button>
            <Button asChild>
              <a href={`${apiBaseUrl}/docs`}>API docs</a>
            </Button>
          </div>
        </header>

        <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <StatCard
            icon={ShieldCheck}
            label="Verification rate"
            value={formatPercent(metrics.verificationRate)}
            detail={`${metrics.verifiedClaims} verified claims`}
          />
          <StatCard
            icon={Activity}
            label="Active runs"
            value={metrics.activeRuns.toString()}
            detail={`${metrics.totalRuns} recent runs tracked`}
          />
          <StatCard
            icon={TimerReset}
            label="P95 latency"
            value={formatSeconds(metrics.p95Latency)}
            detail={`P50 ${formatSeconds(metrics.p50Latency)}`}
          />
          <StatCard
            icon={CircleDollarSign}
            label="Cost"
            value={formatCurrency(metrics.totalCostUsd)}
            detail={`${metrics.totalTokens} tokens recorded`}
          />
        </section>

        <section className="grid gap-4 xl:grid-cols-[minmax(0,2fr)_minmax(320px,1fr)]">
          <RunStatusTable runs={runs} />
          <Card>
            <CardHeader>
              <CardTitle>Current run</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {latest ? (
                <>
                  <div>
                    <p className="text-sm font-medium">{latest.repoName}</p>
                    <p className="mt-1 text-sm leading-6 text-muted-foreground">{latest.query}</p>
                  </div>
                  <div className="grid grid-cols-2 gap-3 text-sm">
                    <KeyValue label="Agent" value={latest.agentName} />
                    <KeyValue label="Tool" value={latest.toolName ?? "none"} />
                    <KeyValue label="Status" value={latest.status} />
                    <KeyValue label="Latency" value={formatSeconds(latest.latency)} />
                  </div>
                  <div className="rounded-md border border-border bg-muted p-3 text-sm leading-6">
                    {latest.finalOutput ?? latest.error ?? "Run is still producing output."}
                  </div>
                </>
              ) : (
                <p className="text-sm text-muted-foreground">No run data available.</p>
              )}
            </CardContent>
          </Card>
        </section>

        <section className="grid gap-4 lg:grid-cols-2 xl:grid-cols-4">
          <MetricList
            icon={<TimerReset className="h-4 w-4" aria-hidden="true" />}
            title="Agent latency"
            rows={latencyRows.map((row) => ({
              label: row.agent,
              value: `P50 ${formatSeconds(row.p50)} / P95 ${formatSeconds(row.p95)}`,
              share: row.runCount / Math.max(1, runs.length),
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
          <MetricList
            icon={<ListChecks className="h-4 w-4" aria-hidden="true" />}
            title="Verification stats"
            rows={[
              { label: "verified", value: metrics.verifiedClaims.toString(), share: metrics.verificationRate },
              {
                label: "unverified",
                value: metrics.unverifiedClaims.toString(),
                share: share(metrics.unverifiedClaims, metrics),
              },
              {
                label: "contradicted",
                value: metrics.contradictedClaims.toString(),
                share: share(metrics.contradictedClaims, metrics),
              },
            ]}
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
        </section>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <RadioTower className="h-4 w-4" aria-hidden="true" />
              Routing flow
            </CardTitle>
          </CardHeader>
          <CardContent className="grid gap-3 md:grid-cols-3">
            {statusRows.map((row) => (
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
            ))}
          </CardContent>
        </Card>
      </div>
    </main>
  );
}

type MetricRow = {
  label: string;
  value: string;
  share: number;
};

function MetricList({
  icon,
  title,
  rows,
}: {
  icon: React.ReactNode;
  title: string;
  rows: MetricRow[];
}) {
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
          <div key={row.label} className="space-y-1.5">
            <div className="flex items-center justify-between gap-3 text-sm">
              <span className="truncate font-medium">{row.label}</span>
              <span className="shrink-0 text-muted-foreground">{row.value}</span>
            </div>
            <div className="h-2 rounded-full bg-muted">
              <div
                className="h-2 rounded-full bg-primary"
                style={{ width: `${Math.max(4, row.share * 100)}%` }}
              />
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

function KeyValue({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs uppercase text-muted-foreground">{label}</p>
      <p className="mt-1 font-medium">{value}</p>
    </div>
  );
}

function share(value: number, metrics: { verifiedClaims: number; unverifiedClaims: number; contradictedClaims: number }) {
  const total = metrics.verifiedClaims + metrics.unverifiedClaims + metrics.contradictedClaims;
  return total === 0 ? 0 : value / total;
}
