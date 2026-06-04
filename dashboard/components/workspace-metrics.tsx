import { AlertTriangle, GitBranch, ListChecks, RadioTower, TimerReset } from "lucide-react";
import type { ReactNode } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatSeconds } from "@/lib/metrics";

type MetricRow = {
  label: string;
  value: string;
  share: number;
};

type WorkspaceMetricsProps = {
  latencyRows: { agent: string; p50: number; p95: number; runCount: number }[];
  routeRows: { label: string; count: number; share: number }[];
  statusRows: { label: string; count: number; share: number }[];
  failureRows: { label: string; count: number; share: number }[];
  verification: {
    verified: number;
    unverified: number;
    contradicted: number;
    verificationRate: number;
  };
};

export function WorkspaceMetrics({
  latencyRows,
  routeRows,
  statusRows,
  failureRows,
  verification,
}: WorkspaceMetricsProps) {
  const claimTotal = verification.verified + verification.unverified + verification.contradicted;

  return (
    <section className="grid gap-4">
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
        <MetricList
          icon={<ListChecks className="h-4 w-4" aria-hidden="true" />}
          title="Verification stats"
          rows={[
            {
              label: "verified",
              value: verification.verified.toString(),
              share: verification.verificationRate,
            },
            {
              label: "unverified",
              value: verification.unverified.toString(),
              share: share(verification.unverified, claimTotal),
            },
            {
              label: "contradicted",
              value: verification.contradicted.toString(),
              share: share(verification.contradicted, claimTotal),
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
      </div>

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
    </section>
  );
}

function MetricList({ icon, title, rows }: { icon: ReactNode; title: string; rows: MetricRow[] }) {
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

function share(value: number, total: number) {
  return total === 0 ? 0 : value / total;
}
