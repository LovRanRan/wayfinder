"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { History } from "lucide-react";

import { RunStatusTable } from "@/components/run-status-table";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { formatDate, timestamp } from "@/lib/format";
import type { DashboardRun, DashboardThread } from "@/lib/types";

type HistoryViewProps = {
  threads: DashboardThread[];
  runs: DashboardRun[];
  source: "api" | "demo";
};

export function HistoryView({ threads, runs, source }: HistoryViewProps) {
  const router = useRouter();
  const [showArchived, setShowArchived] = useState(false);
  const archivedCount = threads.filter((thread) => thread.status === "archived").length;
  const ordered = [...threads]
    .filter((thread) => showArchived || thread.status !== "archived")
    .sort((a, b) => timestamp(b.updatedAt) - timestamp(a.updatedAt));

  return (
    <div className="grid gap-4">
      <section className="rounded-lg border border-border bg-card shadow-sm">
        <header className="flex items-center justify-between gap-2 border-b border-border px-4 py-3">
          <h2 className="text-heading font-semibold">Repo activity timeline</h2>
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground">
              {ordered.length} thread{ordered.length === 1 ? "" : "s"}
            </span>
            {archivedCount > 0 ? (
              <button type="button" onClick={() => setShowArchived((value) => !value)}>
                <Badge variant={showArchived ? "warning" : "outline"}>
                  {showArchived ? "Hide archived" : `Show archived (${archivedCount})`}
                </Badge>
              </button>
            ) : null}
          </div>
        </header>
        <div className="grid gap-2 p-4">
          {ordered.length === 0 ? (
            <EmptyState
              icon={History}
              title="No activity yet"
              description="Open a repo from the Threads page to start a grounded conversation; activity shows up here."
            />
          ) : (
            ordered.map((thread) => {
              const latestRun = thread.activeRun ?? thread.runs[thread.runs.length - 1] ?? null;
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
                      <span className="text-sm font-semibold">{thread.repoName}</span>
                      <span className="ml-2 text-xs text-muted-foreground">
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
                          router.push(`/?thread=${encodeURIComponent(thread.threadId)}`);
                        }}
                      >
                        <Badge variant="success">Open</Badge>
                      </button>
                    </div>
                  </summary>
                  <div className="grid gap-2 border-t border-border px-3 py-2">
                    {events.map((event) => (
                      <div key={event.id} className="rounded-md border border-border bg-card/50 p-2">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <span className="text-xs font-semibold">{event.title}</span>
                          <div className="flex items-center gap-2">
                            <span className="text-[11px] text-muted-foreground">
                              {formatDate(event.createdAt)}
                            </span>
                            {event.run !== null ? (
                              <button
                                type="button"
                                onClick={() =>
                                  router.push(`/?job=${encodeURIComponent(event.run!.jobId)}`)
                                }
                              >
                                <Badge
                                  variant={event.run.status === "failed" ? "danger" : "outline"}
                                >
                                  view report
                                </Badge>
                              </button>
                            ) : null}
                          </div>
                        </div>
                        <p className="mt-1 line-clamp-2 text-[11px] leading-5 text-muted-foreground">
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

      <details className="rounded-lg border border-border bg-card p-4 shadow-sm">
        <summary className="cursor-pointer text-sm font-semibold text-muted-foreground">
          Run diagnostics
        </summary>
        <div className="mt-4">
          <RunStatusTable
            runs={runs}
            source={source}
            onSelectRun={(run) => router.push(`/?job=${encodeURIComponent(run.jobId)}`)}
            selectedJobId={null}
          />
        </div>
      </details>
    </div>
  );
}
