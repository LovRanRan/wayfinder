import { ExternalLink, History, PanelRightOpen } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { formatCurrency, formatSeconds } from "@/lib/metrics";
import type { DashboardRun } from "@/lib/types";

type RunStatusTableProps = {
  runs: DashboardRun[];
  source?: "api" | "demo";
  compact?: boolean;
  selectedJobId?: string | null;
  onSelectRun?: (run: DashboardRun) => void;
};

export function RunStatusTable({
  runs,
  source = "api",
  compact = false,
  selectedJobId = null,
  onSelectRun,
}: RunStatusTableProps) {
  return (
    <section className="overflow-hidden rounded-lg border border-border bg-card">
      <header className="flex items-center justify-between border-b border-border bg-muted/60 px-4 py-3">
        <div className="flex items-center gap-2 font-mono text-sm font-semibold">
          <History className="h-4 w-4 text-primary" aria-hidden="true" />
          Recent runs
        </div>
        <span className="font-mono text-xs text-muted-foreground">{runs.length}</span>
      </header>
      <div className={compact ? "p-2" : "p-4"}>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[760px] border-collapse text-left font-mono text-xs">
            <thead>
              <tr className="border-b border-border uppercase text-muted-foreground">
                <th className="py-3 pr-4 font-medium">Repo</th>
                <th className="py-3 pr-4 font-medium">Status</th>
                <th className="py-3 pr-4 font-medium">Agent</th>
                {!compact ? <th className="py-3 pr-4 font-medium">Intent</th> : null}
                <th className="py-3 pr-4 font-medium">Claims</th>
                <th className="py-3 pr-4 font-medium">Latency</th>
                {!compact ? <th className="py-3 pr-4 font-medium">Cost</th> : null}
                <th className="py-3 pr-4 font-medium">Answer</th>
                <th className="py-3 pr-4 font-medium">Trace</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <tr
                  key={run.jobId}
                  className={
                    run.jobId === selectedJobId
                      ? "cursor-pointer border-b border-border bg-primary/10 last:border-0"
                      : "cursor-pointer border-b border-border hover:bg-muted/40 last:border-0"
                  }
                  onClick={() => onSelectRun?.(run)}
                >
                  <td className="py-3 pr-4 font-medium">
                    {onSelectRun ? (
                      <button
                        type="button"
                        className="max-w-52 truncate text-left text-foreground hover:text-primary"
                        onClick={() => onSelectRun(run)}
                      >
                        {run.repoName}
                      </button>
                    ) : (
                      <span>{run.repoName}</span>
                    )}
                  </td>
                  <td className="py-3 pr-4">
                    <Badge variant={statusVariant(run.status)}>
                      {run.status}
                    </Badge>
                  </td>
                  <td className="py-3 pr-4">{run.agentName}</td>
                  {!compact ? <td className="py-3 pr-4">{run.intent}</td> : null}
                  <td className="py-3 pr-4">
                    <span className="text-success">{run.verifiedCount}</span>
                    <span className="text-muted-foreground"> / </span>
                    <span className="text-warning">{run.unverifiedCount}</span>
                    <span className="text-muted-foreground"> / </span>
                    <span className="text-danger">{run.contradictedCount}</span>
                  </td>
                  <td className="py-3 pr-4">{formatSeconds(run.latency)}</td>
                  {!compact ? <td className="py-3 pr-4">{formatCurrency(run.costUsd)}</td> : null}
                  <td className="py-3 pr-4">
                    <a
                      href={`?job=${encodeURIComponent(run.jobId)}&tab=threads`}
                      className="inline-flex items-center gap-1 text-primary hover:underline"
                      onClick={(event) => {
                        if (event.metaKey || event.ctrlKey || event.shiftKey || event.button !== 0) {
                          return;
                        }
                        event.preventDefault();
                        event.stopPropagation();
                        onSelectRun?.(run);
                      }}
                    >
                      Open
                      <PanelRightOpen className="h-3 w-3" aria-hidden="true" />
                    </a>
                  </td>
                  <td className="py-3 pr-4">
                    {source === "api" && run.traceUrl ? (
                      <a
                        href={run.traceUrl}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 text-primary hover:underline"
                        onClick={(event) => event.stopPropagation()}
                      >
                        Trace
                        <ExternalLink className="h-3 w-3" aria-hidden="true" />
                      </a>
                    ) : source === "demo" ? (
                      <span className="text-muted-foreground">Sample</span>
                    ) : (
                      <span className="text-muted-foreground">Pending</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}

function statusVariant(status: DashboardRun["status"]) {
  if (status === "completed") {
    return "success";
  }
  if (status === "failed") {
    return "danger";
  }
  return "warning";
}
