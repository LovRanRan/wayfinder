"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { CurrentRunConsole } from "@/components/current-run-console";
import { DashboardStats } from "@/components/dashboard-stats";
import { RepoConversationWorkspace } from "@/components/repo-conversation-workspace";
import { RunBriefingPanel } from "@/components/run-briefing-panel";
import { RunLauncher } from "@/components/run-launcher";
import { RunStatusTable } from "@/components/run-status-table";
import { WorkspaceTabs, type WorkspaceTab } from "@/components/workspace-tabs";
import { WorkspaceMetrics } from "@/components/workspace-metrics";
import { WorkspaceSettingsPanel } from "@/components/workspace-settings";
import { buildDashboardMetrics, toDashboardRun } from "@/lib/metrics";
import { upsertThread } from "@/lib/threads";
import type { ApiRunSummary, DashboardRun, DashboardThread, RunStatus } from "@/lib/types";

const activeStatuses: RunStatus[] = ["queued", "running"];

type AgentWorkbenchProps = {
  runs: DashboardRun[];
  threads: DashboardThread[];
  source: "api" | "demo";
  publicApiBaseUrl: string;
};

export function AgentWorkbench({
  runs,
  threads,
  source,
  publicApiBaseUrl,
}: AgentWorkbenchProps) {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const selectedJobId = searchParams.get("job");
  const selectedThreadId = searchParams.get("thread");
  const requestedTab = workspaceTabFromParam(searchParams.get("tab"));
  const [activeTab, setActiveTab] = useState<WorkspaceTab>(() =>
    requestedTab ?? (selectedJobId === null ? "threads" : "answer"),
  );
  const [liveRuns, setLiveRuns] = useState<DashboardRun[]>(runs);
  const [liveThreads, setLiveThreads] = useState<DashboardThread[]>(threads);
  const [selectedRun, setSelectedRun] = useState<DashboardRun | null>(() =>
    runFromJobId(runs, selectedJobId),
  );
  const refreshedCompletedJobsRef = useRef<Set<string>>(new Set());
  const selectedRunJobId = selectedRun?.jobId ?? null;
  const selectedRunStatus = selectedRun?.status ?? null;
  const activeRunCount = useMemo(
    () => liveRuns.filter((run) => activeStatuses.includes(run.status)).length,
    [liveRuns],
  );

  const updateUrl = useCallback(
    (updates: { job?: string | null; thread?: string | null; tab?: WorkspaceTab | null }) => {
      const params = new URLSearchParams(searchParams.toString());
      if (updates.job !== undefined) {
        if (updates.job === null) {
          params.delete("job");
        } else {
          params.set("job", updates.job);
        }
      }
      if (updates.thread !== undefined) {
        if (updates.thread === null) {
          params.delete("thread");
        } else {
          params.set("thread", updates.thread);
        }
      }
      if (updates.tab !== undefined) {
        if (updates.tab === null) {
          params.delete("tab");
        } else if (updates.tab === "run" && !params.has("job")) {
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
      if (run !== null) {
        setLiveRuns((currentRuns) => upsertRun(currentRuns, run));
      }
      updateUrl({ job: run?.jobId ?? null, tab: run === null ? null : "answer" });
      if (run !== null) {
        setActiveTab("answer");
      }
    },
    [updateUrl],
  );

  const syncRun = useCallback((run: DashboardRun | null) => {
    setSelectedRun(run);
    if (run !== null) {
      setLiveRuns((currentRuns) => upsertRun(currentRuns, run));
    }
  }, []);

  const selectThread = useCallback(
    (thread: DashboardThread) => {
      setLiveThreads((currentThreads) => upsertThread(currentThreads, thread));
      updateUrl({ thread: thread.threadId, tab: "threads" });
      setActiveTab("threads");
    },
    [updateUrl],
  );

  useEffect(() => {
    setLiveRuns(runs);
  }, [runs]);

  useEffect(() => {
    setLiveThreads(threads);
  }, [threads]);

  useEffect(() => {
    setSelectedRun((currentRun) => {
      const linkedRun = runFromJobId(liveRuns, selectedJobId);
      if (linkedRun !== null) {
        return linkedRun;
      }

      if (currentRun === null) {
        return null;
      }

      return liveRuns.find((run) => run.jobId === currentRun.jobId) ?? currentRun;
    });
  }, [liveRuns, selectedJobId]);

  useEffect(() => {
    if (requestedTab !== null) {
      setActiveTab(requestedTab);
      return;
    }
    if (selectedJobId !== null) {
      setActiveTab("answer");
      return;
    }
    if (selectedThreadId !== null) {
      setActiveTab("threads");
    }
  }, [requestedTab, selectedJobId, selectedThreadId]);

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
    let timer: number | null = null;
    const schedulePoll = (delayMs: number) => {
      timer = window.setTimeout(() => {
        void pollRun();
      }, delayMs);
    };
    const pollRun = async () => {
      try {
        const response = await fetch(`/api/wayfinder/status/${encodeURIComponent(selectedRunJobId)}`, {
          headers: { "content-type": "application/json" },
        });
        const payload = await response.json().catch(() => null);
        if (cancelled) {
          return;
        }
        if (!response.ok || payload === null) {
          schedulePoll(2500);
          return;
        }
        const nextRun = toDashboardRun(payload as ApiRunSummary);
        setSelectedRun(nextRun);
        setLiveRuns((currentRuns) => upsertRun(currentRuns, nextRun));
        if (activeStatuses.includes(nextRun.status)) {
          schedulePoll(1400);
          return;
        }

        if (!refreshedCompletedJobsRef.current.has(nextRun.jobId)) {
          refreshedCompletedJobsRef.current.add(nextRun.jobId);
          router.refresh();
        }
      } catch {
        // Keep the last known active run visible; manual refresh still reports request errors.
        if (!cancelled) {
          schedulePoll(2500);
        }
      }
    };

    schedulePoll(1400);

    return () => {
      cancelled = true;
      if (timer !== null) {
        window.clearTimeout(timer);
      }
    };
  }, [router, selectedRunJobId, selectedRunStatus, source]);

  useEffect(() => {
    if (source !== "api" || activeRunCount === 0) {
      return;
    }

    let cancelled = false;
    let timer: number | null = null;
    const schedulePoll = (delayMs: number) => {
      timer = window.setTimeout(() => {
        void pollRuns();
      }, delayMs);
    };
    const pollRuns = async () => {
      try {
        const response = await fetch("/api/wayfinder/runs?limit=10", {
          headers: { "content-type": "application/json" },
        });
        const payload = await response.json().catch(() => null);
        if (cancelled || !response.ok || !Array.isArray(payload)) {
          if (!cancelled) {
            schedulePoll(3000);
          }
          return;
        }

        const nextRuns = (payload as ApiRunSummary[]).map(toDashboardRun);
        setLiveRuns(nextRuns);
        if (nextRuns.some((run) => activeStatuses.includes(run.status))) {
          schedulePoll(2500);
        }
      } catch {
        if (!cancelled) {
          schedulePoll(3000);
        }
      }
    };

    schedulePoll(2500);

    return () => {
      cancelled = true;
      if (timer !== null) {
        window.clearTimeout(timer);
      }
    };
  }, [activeRunCount, source]);

  const changeTab = useCallback(
    (tab: WorkspaceTab) => {
      setActiveTab(tab);
      updateUrl({ tab });
    },
    [updateUrl],
  );

  const visibleRuns = useMemo(() => {
    if (selectedRun === null) {
      return liveRuns;
    }

    return [selectedRun, ...liveRuns.filter((run) => run.jobId !== selectedRun.jobId)];
  }, [liveRuns, selectedRun]);

  const metrics = useMemo(() => buildDashboardMetrics(liveRuns), [liveRuns]);

  return (
    <section className="grid gap-4">
      <DashboardStats metrics={metrics} onOpenMetrics={() => changeTab("metrics")} />
      <WorkspaceTabs activeTab={activeTab} onTabChange={changeTab} />

      {activeTab === "threads" ? (
        <RepoConversationWorkspace
          threads={liveThreads}
          selectedThreadId={selectedThreadId}
          source={source}
          onThreadChange={selectThread}
          onRunChange={syncRun}
        />
      ) : null}

      {activeTab === "run" ? (
        <div className="grid gap-4 xl:grid-cols-[minmax(360px,0.74fr)_minmax(0,1.26fr)]">
          <div className="grid gap-4 self-start">
            <RunLauncher initialRun={selectedRun} onRunChange={selectRun} />
          </div>
          <RunBriefingPanel
            runs={visibleRuns}
            selectedRun={selectedRun}
            source={source}
            onOpenAnswer={selectRun}
          />
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

      {activeTab === "metrics" ? <WorkspaceMetrics runs={liveRuns} /> : null}

      {activeTab === "settings" ? <WorkspaceSettingsPanel /> : null}
    </section>
  );
}

function upsertRun(runs: DashboardRun[], nextRun: DashboardRun): DashboardRun[] {
  const withoutRun = runs.filter((run) => run.jobId !== nextRun.jobId);
  return [nextRun, ...withoutRun].sort((a, b) => timestamp(b.createdAt) - timestamp(a.createdAt));
}

function timestamp(value: string): number {
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function runFromJobId(runs: DashboardRun[], jobId: string | null): DashboardRun | null {
  if (jobId === null) {
    return null;
  }
  return runs.find((run) => run.jobId === jobId) ?? null;
}

function workspaceTabFromParam(value: string | null): WorkspaceTab | null {
  if (
    value === "threads" ||
    value === "run" ||
    value === "answer" ||
    value === "history" ||
    value === "metrics" ||
    value === "settings"
  ) {
    return value;
  }
  return null;
}
