"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  CheckCircle2,
  Clock3,
  Database,
  GitBranch,
  History,
  ListChecks,
  PanelRightOpen,
  RadioTower,
  ShieldAlert,
  Terminal,
  type LucideIcon,
} from "lucide-react";

import { RunActivity } from "@/components/run-activity";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { formatSeconds } from "@/lib/metrics";
import type { ApiWorkspaceSettings, DashboardRun, RunStatus, WorkspaceSandboxStatus } from "@/lib/types";

type RunBriefingPanelProps = {
  runs: DashboardRun[];
  selectedRun: DashboardRun | null;
  source: "api" | "demo";
  onOpenAnswer: (run: DashboardRun) => void;
};

type RuntimePolicy = {
  verifierRunner: string;
  sandboxStatus: WorkspaceSandboxStatus;
  sandboxMessage: string;
};

const activeStatuses: RunStatus[] = ["queued", "running"];

export function RunBriefingPanel({ runs, selectedRun, source, onOpenAnswer }: RunBriefingPanelProps) {
  const [runtimePolicy, setRuntimePolicy] = useState<RuntimePolicy | null>(null);
  const focusedRun = selectedRun;
  const activeRunCount = useMemo(
    () => runs.filter((run) => activeStatuses.includes(run.status)).length,
    [runs],
  );
  const recentRuns = runs.slice(0, 5);

  useEffect(() => {
    if (source !== "api") {
      return;
    }

    let cancelled = false;
    async function loadRuntimePolicy() {
      try {
        const response = await fetch("/api/wayfinder/workspace/settings", {
          headers: { "content-type": "application/json" },
        });
        const payload = await response.json().catch(() => null);
        if (!response.ok || payload === null || cancelled) {
          return;
        }
        const settings = payload as ApiWorkspaceSettings;
        setRuntimePolicy({
          verifierRunner: settings.verifier_runner,
          sandboxStatus: settings.sandbox_status,
          sandboxMessage: settings.sandbox_message,
        });
      } catch {
        // Settings has its own tab for request errors; this panel can stay passive.
      }
    }

    void loadRuntimePolicy();
    return () => {
      cancelled = true;
    };
  }, [source]);

  return (
    <section className="grid gap-4">
      <section className="overflow-hidden rounded-lg border border-border bg-card">
        <header className="flex flex-wrap items-start justify-between gap-3 border-b border-border bg-muted/60 px-4 py-3">
          <div>
            <div className="flex items-center gap-2 text-sm font-semibold">
              <Terminal className="h-4 w-4 text-primary" aria-hidden="true" />
              Run briefing
            </div>
            <p className="mt-1 text-xs text-muted-foreground">selected job · runtime boundary</p>
          </div>
          <Badge variant={activeRunCount > 0 ? "warning" : "outline"}>
            {activeRunCount > 0 ? `${activeRunCount} active` : `${runs.length} recent`}
          </Badge>
        </header>

        <div className="grid gap-4 p-4">
          {focusedRun ? (
            <>
              <RunActivity status={focusedRun.status} startedAt={focusedRun.createdAt} label="Polling selected run" />
              <div className="grid gap-3 md:grid-cols-2">
                <BriefingTile icon={GitBranch} label="repo" value={focusedRun.repoName} />
                <BriefingTile
                  icon={Activity}
                  label="status"
                  value={focusedRun.status}
                  tone={statusTone(focusedRun.status)}
                />
                <BriefingTile icon={RadioTower} label="agent" value={focusedRun.agentName} />
                <BriefingTile icon={Clock3} label="latency" value={formatSeconds(focusedRun.latency)} />
                <BriefingTile
                  icon={ListChecks}
                  label="claims"
                  value={`${focusedRun.verifiedCount} / ${focusedRun.unverifiedCount} / ${focusedRun.contradictedCount}`}
                  detail="verified / unverified / contradicted"
                  tone={focusedRun.contradictedCount > 0 ? "danger" : "success"}
                />
                <BriefingTile
                  icon={Database}
                  label="reader mcp"
                  value={focusedRun.mcpServer ?? "pending"}
                  detail={focusedRun.toolName ?? "waiting for tool evidence"}
                />
              </div>
              <div className="rounded-md border border-border bg-muted/40 p-4">
                <div className="flex items-center gap-2 text-[10px] uppercase text-muted-foreground">
                  <Terminal className="h-3.5 w-3.5 text-primary" aria-hidden="true" />
                  query
                </div>
                <p className="mt-2 line-clamp-3 text-sm leading-6 text-foreground">{focusedRun.query}</p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button type="button" onClick={() => onOpenAnswer(focusedRun)}>
                  <PanelRightOpen className="mr-2 h-4 w-4" aria-hidden="true" />
                  Open answer
                </Button>
              </div>
            </>
          ) : (
            <div className="flex items-center gap-2 rounded-md border border-border bg-muted/40 p-4 text-sm text-muted-foreground">
              <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
              Ready
            </div>
          )}
        </div>
      </section>

      <section className="overflow-hidden rounded-lg border border-border bg-card">
        <header className="border-b border-border bg-muted/60 px-4 py-3">
          <div className="flex items-center gap-2 text-sm font-semibold">
            <ShieldAlert className="h-4 w-4 text-primary" aria-hidden="true" />
            Verification boundary
          </div>
          <p className="mt-1 text-xs text-muted-foreground">reader facts · test execution policy</p>
        </header>
        <div className="grid gap-3 p-4 md:grid-cols-2">
          <BriefingTile icon={Database} label="repo reader" value="mcp_http" detail="repo_mapper + ast_explorer" tone="success" />
          <BriefingTile
            icon={ShieldAlert}
            label="test runner"
            value={runtimePolicy?.verifierRunner ?? "placeholder"}
            detail={runtimePolicy?.sandboxMessage ?? "sandbox policy loading"}
            tone={sandboxTone(runtimePolicy?.sandboxStatus)}
          />
          <BriefingTile
            icon={ShieldAlert}
            label="sandbox"
            value={runtimePolicy?.sandboxStatus ?? "unknown"}
            detail="public executable tests are sandbox-gated"
            tone={sandboxTone(runtimePolicy?.sandboxStatus)}
          />
          <BriefingTile icon={History} label="history" value={`${runs.length} runs`} detail="workspace scoped" />
        </div>
      </section>

      <section className="overflow-hidden rounded-lg border border-border bg-card">
        <header className="flex items-center justify-between border-b border-border bg-muted/60 px-4 py-3">
          <div className="flex items-center gap-2 text-sm font-semibold">
            <History className="h-4 w-4 text-primary" aria-hidden="true" />
            Recent answer links
          </div>
          <span className="text-xs text-muted-foreground">{recentRuns.length}</span>
        </header>
        <div className="divide-y divide-border">
          {recentRuns.length > 0 ? (
            recentRuns.map((run) => (
              <button
                key={run.jobId}
                type="button"
                className="grid w-full gap-2 px-4 py-3 text-left hover:bg-muted/40 sm:grid-cols-[minmax(0,1fr)_auto]"
                onClick={() => onOpenAnswer(run)}
              >
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant={statusVariant(run.status)}>{run.status}</Badge>
                    <span className="truncate font-mono text-xs font-semibold text-foreground">{run.repoName}</span>
                  </div>
                  <p className="mt-1 truncate text-[11px] text-muted-foreground">{run.query}</p>
                </div>
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  <span>{run.verifiedCount} / {run.unverifiedCount} / {run.contradictedCount}</span>
                  <PanelRightOpen className="h-3.5 w-3.5 text-primary" aria-hidden="true" />
                </div>
              </button>
            ))
          ) : (
            <div className="px-4 py-3 text-sm text-muted-foreground">No runs yet.</div>
          )}
        </div>
      </section>
    </section>
  );
}

function BriefingTile({
  icon: Icon,
  label,
  value,
  detail,
  tone = "muted",
}: {
  icon: LucideIcon;
  label: string;
  value: string;
  detail?: string;
  tone?: "muted" | "success" | "warning" | "danger";
}) {
  return (
    <div className="min-w-0 rounded-md border border-border bg-muted/40 p-3">
      <div className="flex items-center gap-2">
        <Icon className={tileIconClass(tone)} aria-hidden="true" />
        <span className="text-[10px] uppercase text-muted-foreground">{label}</span>
      </div>
      <p className="mt-2 truncate font-mono text-sm font-semibold text-foreground">{value}</p>
      {detail ? <p className="mt-1 line-clamp-2 text-[11px] leading-5 text-muted-foreground">{detail}</p> : null}
    </div>
  );
}

function statusVariant(status: RunStatus) {
  if (status === "completed") {
    return "success";
  }
  if (status === "failed") {
    return "danger";
  }
  return "warning";
}

function statusTone(status: RunStatus) {
  if (status === "completed") {
    return "success";
  }
  if (status === "failed") {
    return "danger";
  }
  return "warning";
}

function sandboxTone(status: WorkspaceSandboxStatus | undefined) {
  if (status === "enabled") {
    return "success";
  }
  if (status === "disabled" || status === "unavailable") {
    return "warning";
  }
  return "muted";
}

function tileIconClass(tone: "muted" | "success" | "warning" | "danger") {
  const base = "h-4 w-4";
  if (tone === "success") {
    return `${base} text-success`;
  }
  if (tone === "warning") {
    return `${base} text-warning`;
  }
  if (tone === "danger") {
    return `${base} text-danger`;
  }
  return `${base} text-muted-foreground`;
}
