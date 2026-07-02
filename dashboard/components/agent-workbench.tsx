"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { DashboardStats } from "@/components/dashboard-stats";
import { RepoConversationWorkspace } from "@/components/repo-conversation-workspace";
import { buildDashboardMetrics, toDashboardRun } from "@/lib/metrics";
import { timestamp } from "@/lib/format";
import { upsertThread } from "@/lib/threads";
import type { ApiRunSummary, DashboardRun, DashboardThread, RunStatus } from "@/lib/types";

const activeStatuses: RunStatus[] = ["queued", "running"];

type AgentWorkbenchProps = {
  runs: DashboardRun[];
  threads: DashboardThread[];
  source: "api" | "demo";
};

export function AgentWorkbench({ runs, threads, source }: AgentWorkbenchProps) {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const selectedJobId = searchParams.get("job");
  const selectedThreadId = searchParams.get("thread");
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
    (updates: { job?: string | null; thread?: string | null }) => {
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
      const suffix = params.toString();
      router.replace(suffix ? `${pathname}?${suffix}` : pathname, { scroll: false });
    },
    [pathname, router, searchParams],
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
      setSelectedRun(null);
      updateUrl({ job: null, thread: thread.threadId });
    },
    [updateUrl],
  );

  const startNewThread = useCallback(() => {
    setSelectedRun(null);
    updateUrl({ job: null, thread: null });
  }, [updateUrl]);

  const archiveThread = useCallback(
    (threadId: string) => {
      // Mark archived (don't drop it) so it stays available to History; the
      // active thread rail hides it via the status filter.
      setLiveThreads((currentThreads) =>
        currentThreads.map((thread) =>
          thread.threadId === threadId ? { ...thread, status: "archived" } : thread,
        ),
      );
      if (selectedThreadId === threadId) {
        setSelectedRun(null);
        updateUrl({ job: null, thread: null });
      }
    },
    [selectedThreadId, updateUrl],
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

  const metrics = useMemo(() => buildDashboardMetrics(liveRuns), [liveRuns]);

  return (
    <section className="flex min-h-0 flex-1 flex-col gap-4">
      <div className="shrink-0">
        <DashboardStats
          metrics={metrics}
          threads={liveThreads}
          onOpenMetrics={() => router.push("/metrics")}
        />
      </div>

      <div className="min-h-0 flex-1">
        <RepoConversationWorkspace
          threads={liveThreads}
          selectedThreadId={selectedThreadId}
          source={source}
          externalRun={selectedRun}
          onNewThread={startNewThread}
          onThreadChange={selectThread}
          onThreadArchived={archiveThread}
          onRunChange={syncRun}
        />
      </div>
    </section>
  );
}

function upsertRun(runs: DashboardRun[], nextRun: DashboardRun): DashboardRun[] {
  const withoutRun = runs.filter((run) => run.jobId !== nextRun.jobId);
  return [nextRun, ...withoutRun].sort((a, b) => timestamp(b.createdAt) - timestamp(a.createdAt));
}

function runFromJobId(runs: DashboardRun[], jobId: string | null): DashboardRun | null {
  if (jobId === null) {
    return null;
  }
  return runs.find((run) => run.jobId === jobId) ?? null;
}
