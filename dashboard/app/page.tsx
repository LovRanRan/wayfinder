import {
  Activity,
  AlertTriangle,
  CircleDollarSign,
  ExternalLink,
  GitBranch,
  ListChecks,
  RadioTower,
  ShieldCheck,
  TimerReset,
} from "lucide-react";

import { AgentWorkbench } from "@/components/agent-workbench";
import { AuthPanel } from "@/components/auth-panel";
import { StatCard } from "@/components/stat-card";
import { WorkspaceAccount } from "@/components/workspace-account";
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
  const { runs, user, source, publicApiBaseUrl } = await getDashboardData();
  const latest = runs[0];
  const metrics = buildDashboardMetrics(runs);
  const routeRows = groupedCounts(runs, (run) => run.intent);
  const statusRows = groupedCounts(runs, (run) => run.status);
  const latencyRows = latencyByAgent(runs);
  const failureRows = failureModeCounts(runs);

  if (user === null) {
    return (
      <main className="min-h-screen bg-background px-4 py-4 text-foreground md:px-6">
        <div className="mx-auto grid max-w-[1180px] gap-4">
          <header className="flex flex-col gap-3 rounded-lg border border-border bg-card px-4 py-4 md:flex-row md:items-center md:justify-between">
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="success">Wayfinder</Badge>
                <Badge variant={source === "api" ? "warning" : "danger"}>
                  {source === "api" ? "Login required" : "API unavailable"}
                </Badge>
              </div>
              <h1 className="mt-3 font-mono text-xl font-semibold">private codebase onboarding workspace</h1>
              <p className="mt-2 font-mono text-xs text-muted-foreground">api {publicApiBaseUrl}</p>
            </div>
            <Button asChild>
              <a href={`${publicApiBaseUrl}/docs`} target="_blank" rel="noreferrer">
                <ExternalLink className="mr-2 h-4 w-4" aria-hidden="true" />
                API docs
              </a>
            </Button>
          </header>
          <AuthPanel />
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-background px-4 py-4 text-foreground md:px-6">
      <div className="mx-auto flex max-w-[1500px] flex-col gap-4">
        <header className="grid gap-4 rounded-lg border border-border bg-card px-4 py-4 xl:grid-cols-[1fr_360px]">
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <Badge variant="success">Wayfinder workspace</Badge>
              <Badge variant={source === "api" ? "success" : "warning"}>
                {source === "api" ? "Live API" : "Fallback sample"}
              </Badge>
            </div>
            <div>
              <h1 className="font-mono text-xl font-semibold tracking-normal">wayfinder</h1>
              <p className="mt-2 max-w-3xl font-mono text-xs leading-6 text-muted-foreground">
                private run history · repo evidence · verification labels · MCP traces
              </p>
              <p className="mt-1 font-mono text-[11px] text-muted-foreground">api {publicApiBaseUrl}</p>
            </div>
          </div>
          <div className="grid gap-3">
            <WorkspaceAccount user={user} />
            <div className="flex flex-wrap justify-end gap-2">
              {source === "api" && latest?.traceUrl ? (
                <Button variant="outline" asChild>
                  <a href={latest.traceUrl} target="_blank" rel="noreferrer">
                    <ExternalLink className="mr-2 h-4 w-4" aria-hidden="true" />
                    View traces
                  </a>
                </Button>
              ) : (
                <Button variant="outline" disabled>
                  <ExternalLink className="mr-2 h-4 w-4" aria-hidden="true" />
                  Trace pending
                </Button>
              )}
              <Button asChild>
                <a href={`${publicApiBaseUrl}/docs`} target="_blank" rel="noreferrer">
                  <ExternalLink className="mr-2 h-4 w-4" aria-hidden="true" />
                  API docs
                </a>
              </Button>
            </div>
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

        <AgentWorkbench runs={runs} source={source} publicApiBaseUrl={publicApiBaseUrl} />

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

function share(value: number, metrics: { verifiedClaims: number; unverifiedClaims: number; contradictedClaims: number }) {
  const total = metrics.verifiedClaims + metrics.unverifiedClaims + metrics.contradictedClaims;
  return total === 0 ? 0 : value / total;
}
