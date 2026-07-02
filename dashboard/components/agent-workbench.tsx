"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { DashboardStats } from "@/components/dashboard-stats";
import { RepoConversationWorkspace } from "@/components/repo-conversation-workspace";
import { useToast } from "@/components/ui/toast";
import { buildDashboardMetrics, toDashboardRun } from "@/lib/metrics";
import { timestamp } from "@/lib/format";
import { upsertThread } from "@/lib/threads";
import { usePolling } from "@/lib/use-polling";
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
  const { toast } = useToast();
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

  usePolling(
    async ({ schedule, isCancelled, signal }) => {
      if (selectedRunJobId === null) {
        return;
      }
      try {
        const response = await fetch(
          `/api/wayfinder/status/${encodeURIComponent(selectedRunJobId)}`,
          { headers: { "content-type": "application/json" }, signal },
        );
        const payload = await response.json().catch(() => null);
        if (isCancelled()) {
          return;
        }
        if (!response.ok || payload === null) {
          schedule(2500);
          return;
        }
        const nextRun = toDashboardRun(payload as ApiRunSummary);
        setSelectedRun(nextRun);
        setLiveRuns((currentRuns) => upsertRun(currentRuns, nextRun));
        if (activeStatuses.includes(nextRun.status)) {
          schedule(1400);
          return;
        }

        if (!refreshedCompletedJobsRef.current.has(nextRun.jobId)) {
          refreshedCompletedJobsRef.current.add(nextRun.jobId);
          toast({
            variant: nextRun.status === "failed" ? "error" : "success",
            title: nextRun.status === "failed" ? "Run failed" : "Run completed",
            description: `${nextRun.repoUrl} · ${nextRun.verifiedCount} verified · ${nextRun.contradictedCount} contradicted`,
          });
          router.refresh();
        }
      } catch {
        // Keep the last known active run visible; manual refresh still reports request errors.
        if (!isCancelled()) {
          schedule(2500);
        }
      }
    },
    {
      enabled:
        source === "api" &&
        selectedRunJobId !== null &&
        selectedRunStatus !== null &&
        activeStatuses.includes(selectedRunStatus),
      initialDelayMs: 1400,
    },
  );

  usePolling(
    async ({ schedule, isCancelled, signal }) => {
      try {
        const response = await fetch("/api/wayfinder/runs?limit=10", {
          headers: { "content-type": "application/json" },
          signal,
        });
        const payload = await response.json().catch(() => null);
        if (isCancelled() || !response.ok || !Array.isArray(payload)) {
          if (!isCancelled()) {
            schedule(3000);
          }
          return;
        }

        const nextRuns = (payload as ApiRunSummary[]).map(toDashboardRun);
        setLiveRuns(nextRuns);
        if (nextRuns.some((run) => activeStatuses.includes(run.status))) {
          schedule(2500);
        }
      } catch {
        if (!isCancelled()) {
          schedule(3000);
        }
      }
    },
    { enabled: source === "api" && activeRunCount > 0, initialDelayMs: 2500 },
  );

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
