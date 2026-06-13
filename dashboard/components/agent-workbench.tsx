"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { DashboardStats } from "@/components/dashboard-stats";
import { RepoConversationWorkspace } from "@/components/repo-conversation-workspace";
import { RunStatusTable } from "@/components/run-status-table";
import { WorkspaceTabs, type WorkspaceTab } from "@/components/workspace-tabs";
import { WorkspaceMetrics } from "@/components/workspace-metrics";
import { WorkspaceSettingsPanel } from "@/components/workspace-settings";
import { Badge } from "@/components/ui/badge";
import { buildDashboardMetrics, toDashboardRun } from "@/lib/metrics";
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
  const requestedTab = workspaceTabFromParam(searchParams.get("tab"));
  const [activeTab, setActiveTab] = useState<WorkspaceTab>(() =>
    requestedTab ?? "threads",
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
      updateUrl({ job: run?.jobId ?? null, tab: run === null ? null : "threads" });
      if (run !== null) {
        setActiveTab("threads");
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

  const startNewThread = useCallback(() => {
    setSelectedRun(null);
    updateUrl({ job: null, thread: null, tab: "threads" });
    setActiveTab("threads");
  }, [updateUrl]);

  const archiveThread = useCallback(
    (threadId: string) => {
      setLiveThreads((currentThreads) =>
        currentThreads.filter((thread) => thread.threadId !== threadId),
      );
      if (selectedThreadId === threadId) {
        setSelectedRun(null);
        updateUrl({ job: null, thread: null, tab: "threads" });
      }
      setActiveTab("threads");
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
    if (requestedTab !== null) {
      setActiveTab(requestedTab);
      return;
    }
    if (selectedJobId !== null || selectedThreadId !== null) {
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
    <section className="flex min-h-0 flex-1 flex-col gap-4">
      <div className="shrink-0">
        <DashboardStats
          metrics={metrics}
          threads={liveThreads}
          onOpenMetrics={() => changeTab("metrics")}
        />
      </div>
      <div className="shrink-0">
        <WorkspaceTabs activeTab={activeTab} onTabChange={changeTab} />
      </div>

      {activeTab === "threads" ? (
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
      ) : (
        <div className="min-h-0 flex-1 overflow-y-auto">
          {activeTab === "history" ? (
            <div className="grid gap-4">
              <ThreadActivityTimeline
                threads={liveThreads}
                onSelectRun={selectRun}
                onOpenThread={selectThread}
              />
              <details className="rounded-lg border border-border bg-card p-4">
                <summary className="cursor-pointer font-mono text-sm font-semibold text-muted-foreground">
                  Run diagnostics
                </summary>
                <div className="mt-4">
                  <RunStatusTable
                    runs={visibleRuns}
                    source={source}
                    onSelectRun={selectRun}
                    selectedJobId={selectedRun?.jobId ?? null}
                  />
                </div>
              </details>
            </div>
          ) : null}

          {activeTab === "metrics" ? <WorkspaceMetrics runs={liveRuns} /> : null}

          {activeTab === "settings" ? <WorkspaceSettingsPanel /> : null}
        </div>
      )}
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
    value === "history" ||
    value === "metrics" ||
    value === "settings"
  ) {
    return value;
  }
  return null;
}

function ThreadActivityTimeline({
  threads,
  onSelectRun,
  onOpenThread,
}: {
  threads: DashboardThread[];
  onSelectRun: (run: DashboardRun | null) => void;
  onOpenThread: (thread: DashboardThread) => void;
}) {
  const ordered = [...threads].sort((a, b) => timestamp(b.updatedAt) - timestamp(a.updatedAt));

  return (
    <section className="rounded-lg border border-border bg-card">
      <header className="flex items-center justify-between border-b border-border bg-muted/60 px-4 py-3">
        <div className="font-mono text-sm font-semibold">Repo activity timeline</div>
        <span className="font-mono text-xs text-muted-foreground">
          {threads.length} thread{threads.length === 1 ? "" : "s"}
        </span>
      </header>
      <div className="grid gap-2 p-4">
        {ordered.length === 0 ? (
          <div className="rounded-md border border-border bg-background p-3 font-mono text-sm text-muted-foreground">
            No repo conversation activity yet.
          </div>
        ) : (
          ordered.map((thread) => {
            const latestRun =
              thread.activeRun ?? thread.runs[thread.runs.length - 1] ?? null;
            const events = [
              ...thread.messages.map((message) => ({
                id: message.messageId,
                createdAt: message.createdAt,
                title: `${message.role} message`,
                detail: message.content,
                run: message.sourceRunId
                  ? (thread.runs.find((run) => run.jobId === message.sourceRunId) ?? null)
                  : null,
              })),
              {
                id: `${thread.threadId}:created`,
                createdAt: thread.createdAt,
                title: "Repo context attached",
                detail: thread.repoUrl,
                run: null as DashboardRun | null,
              },
            ].sort((a, b) => timestamp(b.createdAt) - timestamp(a.createdAt));

            return (
              <details
                key={thread.threadId}
                className="rounded-md border border-border bg-background"
              >
                <summary className="flex cursor-pointer flex-wrap items-center justify-between gap-2 px-3 py-3">
                  <div className="min-w-0">
                    <span className="font-mono text-sm font-semibold">{thread.repoName}</span>
                    <span className="ml-2 font-mono text-xs text-muted-foreground">
                      {thread.messages.length} msg · {formatDate(thread.updatedAt)}
                    </span>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant="outline">{thread.status}</Badge>
                    {latestRun !== null ? (
                      <span className="font-mono text-xs text-muted-foreground">
                        <span className="text-success">{latestRun.verifiedCount}✓</span>{" "}
                        <span className="text-warning">{latestRun.unverifiedCount}⚠</span>{" "}
                        <span className="text-danger">{latestRun.contradictedCount}✗</span>
                      </span>
                    ) : null}
                    <button
                      type="button"
                      onClick={(event) => {
                        event.preventDefault();
                        event.stopPropagation();
                        onOpenThread(thread);
                      }}
                    >
                      <Badge variant="success">Open</Badge>
                    </button>
                  </div>
                </summary>
                <div className="grid gap-2 border-t border-border px-3 py-2">
                  {events.map((event) => (
                    <div
                      key={event.id}
                      className="rounded-md border border-border bg-card/50 p-2"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <span className="font-mono text-xs font-semibold">{event.title}</span>
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-[11px] text-muted-foreground">
                            {formatDate(event.createdAt)}
                          </span>
                          {event.run !== null ? (
                            <button type="button" onClick={() => onSelectRun(event.run)}>
                              <Badge
                                variant={event.run.status === "failed" ? "danger" : "outline"}
                              >
                                view report
                              </Badge>
                            </button>
                          ) : null}
                        </div>
                      </div>
                      <p className="mt-1 line-clamp-2 font-mono text-[11px] leading-5 text-muted-foreground">
                        {event.detail}
                      </p>
                    </div>
                  ))}
                </div>
              </details>
            );
          })
        )}
      </div>
    </section>
  );
}

function formatDate(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return "unknown time";
  }
  return parsed.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
