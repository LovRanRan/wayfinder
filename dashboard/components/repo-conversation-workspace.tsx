"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  Bot,
  GitBranch,
  Loader2,
  MessageSquare,
  Plus,
  RefreshCw,
  Send,
  User,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { RunActivity } from "@/components/run-activity";
import { toDashboardThread, upsertThread } from "@/lib/threads";
import type {
  ApiConversationThreadDetail,
  DashboardRun,
  DashboardThread,
  DashboardThreadMessage,
  RunStatus,
  ThreadStatus,
} from "@/lib/types";

const activeRunStatuses: RunStatus[] = ["queued", "running"];

type RepoConversationWorkspaceProps = {
  threads: DashboardThread[];
  selectedThreadId: string | null;
  source: "api" | "demo";
  onThreadChange: (thread: DashboardThread) => void;
  onRunChange: (run: DashboardRun | null) => void;
};

export function RepoConversationWorkspace({
  threads,
  selectedThreadId,
  source,
  onThreadChange,
  onRunChange,
}: RepoConversationWorkspaceProps) {
  const selectedThread = useMemo(
    () => threadFromId(threads, selectedThreadId) ?? threads[0] ?? null,
    [selectedThreadId, threads],
  );
  const [repoUrl, setRepoUrl] = useState("");
  const [initialQuery, setInitialQuery] = useState("");
  const [followup, setFollowup] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const activeRun = selectedThread?.activeRun ?? null;
  const activeRunStatus = activeRun?.status ?? null;

  useEffect(() => {
    if (
      source !== "api" ||
      selectedThread === null ||
      activeRunStatus === null ||
      !activeRunStatuses.includes(activeRunStatus)
    ) {
      return;
    }

    let cancelled = false;
    let timer: number | null = null;
    const pollThread = async () => {
      try {
        const nextThread = await fetchThreadDetail(selectedThread.threadId);
        if (cancelled) {
          return;
        }
        onThreadChange(nextThread);
        if (nextThread.activeRun !== null) {
          onRunChange(nextThread.activeRun);
        }
        if (nextThread.activeRun !== null && activeRunStatuses.includes(nextThread.activeRun.status)) {
          timer = window.setTimeout(() => void pollThread(), 1400);
        }
      } catch {
        if (!cancelled) {
          timer = window.setTimeout(() => void pollThread(), 2500);
        }
      }
    };

    timer = window.setTimeout(() => void pollThread(), 1400);

    return () => {
      cancelled = true;
      if (timer !== null) {
        window.clearTimeout(timer);
      }
    };
  }, [activeRunStatus, onRunChange, onThreadChange, selectedThread, source]);

  async function createThread(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsCreating(true);
    setError(null);

    try {
      const nextThread = await postThread("/api/wayfinder/threads", {
        repo_url: repoUrl.trim(),
        initial_query: initialQuery.trim(),
      });
      onThreadChange(nextThread);
      if (nextThread.activeRun !== null) {
        onRunChange(nextThread.activeRun);
      }
      setRepoUrl("");
      setInitialQuery("");
    } catch (createError) {
      setError(errorMessage(createError));
    } finally {
      setIsCreating(false);
    }
  }

  async function sendFollowup(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (selectedThread === null) {
      return;
    }

    setIsSending(true);
    setError(null);

    try {
      const nextThread = await postThread(
        `/api/wayfinder/threads/${encodeURIComponent(selectedThread.threadId)}/messages`,
        { content: followup.trim() },
      );
      onThreadChange(nextThread);
      if (nextThread.activeRun !== null) {
        onRunChange(nextThread.activeRun);
      }
      setFollowup("");
    } catch (sendError) {
      setError(errorMessage(sendError));
    } finally {
      setIsSending(false);
    }
  }

  async function refreshSelectedThread() {
    if (selectedThread === null) {
      return;
    }
    setIsRefreshing(true);
    setError(null);
    try {
      const nextThread = await fetchThreadDetail(selectedThread.threadId);
      onThreadChange(nextThread);
      if (nextThread.activeRun !== null) {
        onRunChange(nextThread.activeRun);
      }
    } catch (refreshError) {
      setError(errorMessage(refreshError));
    } finally {
      setIsRefreshing(false);
    }
  }

  const canCreate = repoUrl.trim().length > 0 && initialQuery.trim().length > 0 && !isCreating;
  const canSend =
    selectedThread !== null &&
    followup.trim().length > 0 &&
    !isSending &&
    selectedThread.status !== "running";

  return (
    <section className="grid gap-4 xl:grid-cols-[340px_minmax(0,1fr)]">
      <aside className="grid gap-4 self-start">
        <section className="overflow-hidden rounded-lg border border-border bg-card">
          <header className="border-b border-border bg-muted/60 px-4 py-3">
            <div className="flex items-center gap-2 font-mono text-sm font-semibold">
              <Plus className="h-4 w-4 text-primary" aria-hidden="true" />
              New repo thread
            </div>
          </header>
          <form className="grid gap-3 p-4" onSubmit={createThread}>
            <label className="grid gap-1.5 font-mono text-xs uppercase text-muted-foreground">
              repo
              <input
                className="h-10 rounded-md border border-border bg-background px-3 font-mono text-sm normal-case text-foreground outline-none transition placeholder:text-muted-foreground focus:border-primary"
                value={repoUrl}
                onChange={(event) => setRepoUrl(event.target.value)}
                placeholder="https://github.com/owner/repo"
              />
            </label>
            <label className="grid gap-1.5 font-mono text-xs uppercase text-muted-foreground">
              first question
              <textarea
                className="min-h-28 resize-y rounded-md border border-border bg-background px-3 py-2 font-mono text-sm normal-case leading-6 text-foreground outline-none transition placeholder:text-muted-foreground focus:border-primary"
                value={initialQuery}
                onChange={(event) => setInitialQuery(event.target.value)}
                placeholder="Map architecture and explain runnable entry points"
              />
            </label>
            <Button type="submit" disabled={!canCreate}>
              {isCreating ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />
              ) : (
                <MessageSquare className="mr-2 h-4 w-4" aria-hidden="true" />
              )}
              Create thread
            </Button>
          </form>
        </section>

        <section className="overflow-hidden rounded-lg border border-border bg-card">
          <header className="flex items-center justify-between border-b border-border bg-muted/60 px-4 py-3">
            <div className="font-mono text-sm font-semibold">Repo threads</div>
            <Badge variant="outline">{threads.length}</Badge>
          </header>
          <div className="max-h-[520px] overflow-y-auto p-2">
            {threads.length === 0 ? (
              <div className="rounded-md border border-border bg-muted/50 p-3 font-mono text-xs leading-5 text-muted-foreground">
                No repo threads yet.
              </div>
            ) : (
              threads.map((thread) => (
                <button
                  key={thread.threadId}
                  type="button"
                  className={
                    thread.threadId === selectedThread?.threadId
                      ? "w-full rounded-md border border-primary bg-primary/10 p-3 text-left"
                      : "w-full rounded-md border border-transparent p-3 text-left hover:border-border hover:bg-muted/50"
                  }
                  onClick={() => onThreadChange(thread)}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="min-w-0 truncate font-mono text-sm font-medium">
                      {thread.title}
                    </span>
                    <Badge variant={threadStatusVariant(thread.status)}>{thread.status}</Badge>
                  </div>
                  <div className="mt-2 truncate font-mono text-xs text-muted-foreground">
                    {thread.repoName}
                  </div>
                  <div className="mt-1 font-mono text-[11px] text-muted-foreground">
                    {thread.messages.length} messages · {formatDate(thread.updatedAt)}
                  </div>
                </button>
              ))
            )}
          </div>
        </section>
      </aside>

      <section className="min-h-[720px] overflow-hidden rounded-lg border border-border bg-card">
        {selectedThread === null ? (
          <div className="flex min-h-[420px] items-center justify-center p-6 text-center font-mono text-sm text-muted-foreground">
            Create a repo thread to start a grounded conversation.
          </div>
        ) : (
          <div className="grid min-h-[720px] grid-rows-[auto_1fr_auto]">
            <header className="border-b border-border bg-muted/60 px-4 py-3">
              <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant={threadStatusVariant(selectedThread.status)}>
                      {selectedThread.status}
                    </Badge>
                    <Badge variant="outline">{selectedThread.repoName}</Badge>
                  </div>
                  <h2 className="mt-2 truncate font-mono text-lg font-semibold">
                    {selectedThread.title}
                  </h2>
                  <p className="mt-1 truncate font-mono text-xs text-muted-foreground">
                    {selectedThread.repoUrl}
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    disabled={isRefreshing}
                    onClick={() => void refreshSelectedThread()}
                  >
                    {isRefreshing ? (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />
                    ) : (
                      <RefreshCw className="mr-2 h-4 w-4" aria-hidden="true" />
                    )}
                    Refresh
                  </Button>
                </div>
              </div>
              {activeRun !== null ? (
                <div className="mt-3 rounded-md border border-border bg-background p-3">
                  <RunActivity status={activeRun.status} startedAt={activeRun.createdAt} />
                </div>
              ) : null}
            </header>

            <div className="overflow-y-auto px-4 py-4">
              <div className="mx-auto grid max-w-4xl gap-3">
                {selectedThread.messages.map((message) => (
                  <ThreadMessageRow
                    key={message.messageId}
                    message={message}
                    linkedRun={runFromMessage(selectedThread.runs, message)}
                  />
                ))}
              </div>
            </div>

            <div className="border-t border-border bg-muted/40 p-4">
              {error ? (
                <div className="mb-3 flex gap-2 rounded-md border border-danger/30 bg-danger/10 p-3 text-sm leading-6 text-danger">
                  <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
                  <span>{error}</span>
                </div>
              ) : null}
              <form className="mx-auto grid max-w-4xl gap-2" onSubmit={sendFollowup}>
                <textarea
                  className="min-h-24 resize-y rounded-md border border-border bg-background px-3 py-2 font-mono text-sm leading-6 text-foreground outline-none transition placeholder:text-muted-foreground focus:border-primary"
                  value={followup}
                  onChange={(event) => setFollowup(event.target.value)}
                  placeholder="Ask a follow-up grounded in this repo thread"
                />
                <div className="flex items-center justify-between gap-3">
                  <p className="font-mono text-[11px] leading-5 text-muted-foreground">
                    Follow-ups reuse this repo and bounded thread memory.
                  </p>
                  <Button type="submit" disabled={!canSend}>
                    {isSending ? (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />
                    ) : (
                      <Send className="mr-2 h-4 w-4" aria-hidden="true" />
                    )}
                    Send
                  </Button>
                </div>
              </form>
            </div>
          </div>
        )}
      </section>
    </section>
  );
}

function ThreadMessageRow({
  message,
  linkedRun,
}: {
  message: DashboardThreadMessage;
  linkedRun: DashboardRun | null;
}) {
  const Icon = message.role === "user" ? User : message.role === "assistant" ? Bot : GitBranch;
  return (
    <article
      className={
        message.role === "user"
          ? "ml-auto max-w-[86%] rounded-lg border border-primary/30 bg-primary/10 p-3"
          : "mr-auto max-w-[92%] rounded-lg border border-border bg-background p-3"
      }
    >
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <Icon className="h-4 w-4 text-primary" aria-hidden="true" />
        <span className="font-mono text-xs uppercase text-muted-foreground">{message.role}</span>
        <span className="font-mono text-[11px] text-muted-foreground">
          {formatDate(message.createdAt)}
        </span>
      </div>
      <div className="whitespace-pre-wrap break-words font-mono text-sm leading-6 text-foreground">
        {message.content}
      </div>
      {linkedRun !== null ? (
        <div className="mt-3 flex flex-wrap gap-2">
          <Badge variant={runStatusVariant(linkedRun.status)}>run {linkedRun.status}</Badge>
          <Badge variant="success">verified {message.verifiedCount}</Badge>
          <Badge variant="warning">unverified {message.unverifiedCount}</Badge>
          <Badge variant={message.contradictedCount > 0 ? "danger" : "outline"}>
            contradicted {message.contradictedCount}
          </Badge>
          {message.evidenceRefs.slice(0, 3).map((ref) => (
            <Badge key={ref} variant="outline">
              {ref}
            </Badge>
          ))}
        </div>
      ) : null}
    </article>
  );
}

async function fetchThreadDetail(threadId: string): Promise<DashboardThread> {
  return postThread(`/api/wayfinder/threads/${encodeURIComponent(threadId)}`, undefined, "GET");
}

async function postThread(
  url: string,
  body: Record<string, unknown> | undefined,
  method: "GET" | "POST" = "POST",
): Promise<DashboardThread> {
  const response = await fetch(url, {
    method,
    headers: { "content-type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  const payload = await response.json().catch(() => null);

  if (!response.ok) {
    throw new Error(detailFromPayload(payload) ?? response.statusText);
  }

  return toDashboardThread(payload as ApiConversationThreadDetail);
}

function detailFromPayload(payload: unknown): string | null {
  if (payload !== null && typeof payload === "object") {
    const detail = (payload as { detail?: unknown }).detail;
    return typeof detail === "string" ? detail : null;
  }
  return null;
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Wayfinder thread request failed.";
}

function threadFromId(threads: DashboardThread[], threadId: string | null): DashboardThread | null {
  if (threadId === null) {
    return null;
  }
  return threads.find((thread) => thread.threadId === threadId) ?? null;
}

function runFromMessage(
  runs: DashboardRun[],
  message: DashboardThreadMessage,
): DashboardRun | null {
  if (message.sourceRunId === null) {
    return null;
  }
  return runs.find((run) => run.jobId === message.sourceRunId) ?? null;
}

function threadStatusVariant(status: ThreadStatus): "success" | "warning" | "danger" | "outline" {
  if (status === "active") {
    return "success";
  }
  if (status === "running") {
    return "warning";
  }
  if (status === "failed") {
    return "danger";
  }
  return "outline";
}

function runStatusVariant(status: RunStatus): "success" | "warning" | "danger" | "outline" {
  if (status === "completed") {
    return "success";
  }
  if (status === "queued" || status === "running") {
    return "warning";
  }
  if (status === "failed") {
    return "danger";
  }
  return "outline";
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

export function mergeThreadList(
  threads: DashboardThread[],
  nextThread: DashboardThread,
): DashboardThread[] {
  return upsertThread(threads, nextThread);
}
