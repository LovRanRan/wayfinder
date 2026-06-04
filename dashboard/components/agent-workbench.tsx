"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { CurrentRunConsole } from "@/components/current-run-console";
import { RunLauncher } from "@/components/run-launcher";
import { RunStatusTable } from "@/components/run-status-table";
import { WorkspaceTabs, type WorkspaceTab } from "@/components/workspace-tabs";
import { WorkspaceMetrics } from "@/components/workspace-metrics";
import { toDashboardRun } from "@/lib/metrics";
import type { ApiRunSummary, DashboardRun, RunStatus } from "@/lib/types";

const activeStatuses: RunStatus[] = ["queued", "running"];

type AgentWorkbenchProps = {
  runs: DashboardRun[];
  source: "api" | "demo";
  publicApiBaseUrl: string;
  metrics: {
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
};

export function AgentWorkbench({ runs, source, publicApiBaseUrl, metrics }: AgentWorkbenchProps) {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const selectedJobId = searchParams.get("job");
  const requestedTab = workspaceTabFromParam(searchParams.get("tab"));
  const [activeTab, setActiveTab] = useState<WorkspaceTab>(() => requestedTab ?? "run");
  const [selectedRun, setSelectedRun] = useState<DashboardRun | null>(() =>
    runFromJobId(runs, selectedJobId) ?? runs[0] ?? null,
  );
  const selectedRunJobId = selectedRun?.jobId ?? null;
  const selectedRunStatus = selectedRun?.status ?? null;

  const updateUrl = useCallback(
    (updates: { job?: string | null; tab?: WorkspaceTab | null }) => {
      const params = new URLSearchParams(searchParams.toString());
      if (updates.job !== undefined) {
        if (updates.job === null) {
          params.delete("job");
        } else {
          params.set("job", updates.job);
        }
      }
      if (updates.tab !== undefined) {
        if (updates.tab === null || updates.tab === "run") {
          params.delete("tab");
        } else {
          params.set("tab", updates.tab);
        }
      }
      const suffix = params.toString();
      router.replace(suffix ? `${pathname}?${suffix}` : pathname, { scroll: false });
    },
    [pathname, router, searchParams],
  );

  const selectRun = useCallback(
    (run: DashboardRun | null) => {
      setSelectedRun(run);
      updateUrl({ job: run?.jobId ?? null, tab: run === null ? null : "answer" });
      if (run !== null) {
        setActiveTab("answer");
      }
    },
    [updateUrl],
  );

  useEffect(() => {
    setSelectedRun((currentRun) => {
      const linkedRun = runFromJobId(runs, selectedJobId);
      if (linkedRun !== null) {
        return linkedRun;
      }

      if (currentRun === null) {
        return runs[0] ?? null;
      }

      return runs.find((run) => run.jobId === currentRun.jobId) ?? currentRun;
    });
  }, [runs, selectedJobId]);

  useEffect(() => {
    if (requestedTab !== null) {
      setActiveTab(requestedTab);
    }
  }, [requestedTab]);

  useEffect(() => {
    if (
      source !== "api" ||
      selectedRunJobId === null ||
      selectedRunStatus === null ||
      !activeStatuses.includes(selectedRunStatus)
    ) {
      return;
    }

    let cancelled = false;
    const timer = window.setTimeout(async () => {
      try {
        const response = await fetch(`/api/wayfinder/status/${encodeURIComponent(selectedRunJobId)}`, {
          headers: { "content-type": "application/json" },
        });
        const payload = await response.json().catch(() => null);
        if (!response.ok || payload === null || cancelled) {
          return;
        }
        setSelectedRun(toDashboardRun(payload as ApiRunSummary));
      } catch {
        // Keep the last known active run visible; manual refresh still reports request errors.
      }
    }, 1400);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [selectedRunJobId, selectedRunStatus, source]);

  const changeTab = useCallback(
    (tab: WorkspaceTab) => {
      setActiveTab(tab);
      updateUrl({ tab });
    },
    [updateUrl],
  );

  const visibleRuns = useMemo(() => {
    if (selectedRun === null) {
      return runs;
    }

    return [selectedRun, ...runs.filter((run) => run.jobId !== selectedRun.jobId)];
  }, [runs, selectedRun]);

  return (
    <section className="grid gap-4">
      <WorkspaceTabs activeTab={activeTab} onTabChange={changeTab} />

      {activeTab === "run" ? (
        <div className="grid gap-4 xl:grid-cols-[minmax(360px,0.74fr)_minmax(0,1.26fr)]">
          <div className="grid gap-4 self-start">
            <RunLauncher initialRun={selectedRun} onRunChange={selectRun} />
          </div>
          <CurrentRunConsole run={selectedRun} publicApiBaseUrl={publicApiBaseUrl} source={source} />
        </div>
      ) : null}

      {activeTab === "answer" ? (
        <CurrentRunConsole run={selectedRun} publicApiBaseUrl={publicApiBaseUrl} source={source} />
      ) : null}

      {activeTab === "history" ? (
        <div className="grid gap-4">
          <RunStatusTable
            runs={visibleRuns}
            source={source}
            onSelectRun={selectRun}
            selectedJobId={selectedRun?.jobId ?? null}
          />
        </div>
      ) : null}

      {activeTab === "metrics" ? <WorkspaceMetrics {...metrics} /> : null}
    </section>
  );
}

function runFromJobId(runs: DashboardRun[], jobId: string | null): DashboardRun | null {
  if (jobId === null) {
    return null;
  }
  return runs.find((run) => run.jobId === jobId) ?? null;
}

function workspaceTabFromParam(value: string | null): WorkspaceTab | null {
  if (value === "run" || value === "answer" || value === "history" || value === "metrics") {
    return value;
  }
  return null;
}
