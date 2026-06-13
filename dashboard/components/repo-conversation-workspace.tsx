"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  Archive,
  Bot,
  BrainCircuit,
  GitBranch,
  Loader2,
  PanelRight,
  Plus,
  RefreshCw,
  Send,
  User,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { CurrentRunConsole } from "@/components/current-run-console";
import { RunActivity } from "@/components/run-activity";
import { toActiveRepoContext, toChatResponse } from "@/lib/chat";
import { toDashboardThread, upsertThread } from "@/lib/threads";
import type {
  ActiveRepoContext,
  AgentTraceAttachment,
  ApiActiveRepoContext,
  ApiChatResponse,
  ApiConversationThreadDetail,
  ChatAnswerMode,
  ChatResponse,
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
  onNewThread: () => void;
  onThreadChange: (thread: DashboardThread) => void;
  onThreadArchived: (threadId: string) => void;
  onRunChange: (run: DashboardRun | null) => void;
};

export function RepoConversationWorkspace({
  threads,
  selectedThreadId,
  source,
  onNewThread,
  onThreadChange,
  onThreadArchived,
  onRunChange,
}: RepoConversationWorkspaceProps) {
  const [isNewThreadMode, setIsNewThreadMode] = useState(false);
  const selectedThread = useMemo(
    () =>
      selectedThreadId === null && isNewThreadMode
        ? null
        : threadFromId(threads, selectedThreadId) ?? threads[0] ?? null,
    [isNewThreadMode, selectedThreadId, threads],
  );
  const [chatDraft, setChatDraft] = useState("");
  const [answerMode, setAnswerMode] = useState<ChatAnswerMode>("auto");
  const [activeContext, setActiveContext] = useState<ActiveRepoContext | null>(() =>
    contextFromThread(selectedThread),
  );
  const [agentTrace, setAgentTrace] = useState<AgentTraceAttachment | null>(null);
  const [selectedAttachmentRun, setSelectedAttachmentRun] = useState<DashboardRun | null>(
    selectedThread?.activeRun ?? null,
  );
  const [error, setError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [pendingUserMessage, setPendingUserMessage] = useState<string | null>(null);
  const [isSending, setIsSending] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isClearingContext, setIsClearingContext] = useState(false);
  const [archivingThreadId, setArchivingThreadId] = useState<string | null>(null);
  const activeRun = selectedThread?.activeRun ?? selectedAttachmentRun;
  const activeRunStatus = activeRun?.status ?? null;
  const sendBlocker = sendDisabledReason({
    draft: chatDraft,
    selectedThread,
    isSending,
    hasActiveRepo: Boolean(activeContext?.repoUrl),
  });
  const canSend = sendBlocker === null;
  const hasVisibleMessages =
    (selectedThread?.messages.length ?? 0) > 0 || pendingUserMessage !== null;

  useEffect(() => {
    if (selectedThread !== null) {
      setActiveContext((current) => current ?? contextFromThread(selectedThread));
      setSelectedAttachmentRun(selectedThread.activeRun);
    }
  }, [selectedThread]);

  useEffect(() => {
    if (selectedThreadId !== null) {
      setIsNewThreadMode(false);
    }
  }, [selectedThreadId]);

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
          setSelectedAttachmentRun(nextThread.activeRun);
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

  async function sendChat(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canSend) {
      return;
    }

    const nextContent = chatDraft.trim();
    setIsSending(true);
    setError(null);
    setStatusMessage("Sending message to Wayfinder...");
    setPendingUserMessage(nextContent);

    try {
      const response = await postChat({
        content: nextContent,
        thread_id: selectedThread?.threadId ?? null,
        answer_mode: answerMode,
      });
      setActiveContext(response.activeContext);
      setAgentTrace(response.agentTrace);
      if (response.thread !== null) {
        setIsNewThreadMode(false);
        onThreadChange(response.thread);
      }
      if (response.activeRun !== null) {
        onRunChange(response.activeRun);
        setSelectedAttachmentRun(response.activeRun);
      }
      setChatDraft("");
      setStatusMessage(statusMessageFromChatResponse(response));
    } catch (sendError) {
      setError(errorMessage(sendError));
      setStatusMessage(null);
    } finally {
      setIsSending(false);
      setPendingUserMessage(null);
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
        setSelectedAttachmentRun(nextThread.activeRun);
      }
      setActiveContext(contextFromThread(nextThread));
    } catch (refreshError) {
      setError(errorMessage(refreshError));
    } finally {
      setIsRefreshing(false);
    }
  }

  async function startNewThread() {
    setIsClearingContext(true);
    setError(null);
    try {
      const context = await clearWorkspaceContext();
      setActiveContext(context);
      setAgentTrace(null);
      setSelectedAttachmentRun(null);
      setChatDraft("");
      setStatusMessage("Ready for a new repo context.");
      setIsNewThreadMode(true);
      onNewThread();
      onRunChange(null);
    } catch (clearError) {
      setError(errorMessage(clearError));
    } finally {
      setIsClearingContext(false);
    }
  }

  async function archiveThread(thread: DashboardThread) {
    setArchivingThreadId(thread.threadId);
    setError(null);
    try {
      const context = await deleteThread(thread.threadId);
      if (selectedThread?.threadId === thread.threadId) {
        setActiveContext(context);
        setAgentTrace(null);
        setSelectedAttachmentRun(null);
        setIsNewThreadMode(true);
        onRunChange(null);
      }
      onThreadArchived(thread.threadId);
      setStatusMessage(`Archived ${thread.repoName}.`);
    } catch (archiveError) {
      setError(errorMessage(archiveError));
    } finally {
      setArchivingThreadId(null);
    }
  }

  return (
    <section className="grid h-full min-h-0 gap-4 xl:grid-cols-[290px_minmax(0,1fr)_320px]">
      <aside className="grid min-h-0 grid-rows-[auto_1fr] gap-4">
        <section className="rounded-lg border border-border bg-card p-4">
          <div className="flex items-center gap-2 font-mono text-sm font-semibold">
            <GitBranch className="h-4 w-4 text-primary" aria-hidden="true" />
            Active repo
          </div>
          <div className="mt-3 rounded-md border border-border bg-background p-3">
            <div className="truncate font-mono text-sm font-semibold">
              {activeContext?.repoName ?? "No repo selected"}
            </div>
            <p className="mt-1 line-clamp-2 break-all font-mono text-[11px] leading-5 text-muted-foreground">
              {activeContext?.repoUrl ?? "Paste a GitHub URL or owner/repo in chat."}
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              <Badge variant={contextStatusVariant(activeContext?.status ?? "empty")}>
                {activeContext?.status ?? "empty"}
              </Badge>
              {activeContext?.activeFocus ? (
                <Badge variant="outline">{activeContext.activeFocus}</Badge>
              ) : null}
            </div>
          </div>
        </section>

        <section className="min-h-0 overflow-hidden rounded-lg border border-border bg-card">
          <header className="flex items-center justify-between gap-3 border-b border-border bg-muted/60 px-4 py-3">
            <div className="font-mono text-sm font-semibold">Repo threads</div>
            <div className="flex items-center gap-2">
              <Badge variant="outline">{threads.length}</Badge>
              <Button
                type="button"
                variant="outline"
                disabled={isClearingContext}
                onClick={() => void startNewThread()}
              >
                {isClearingContext ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />
                ) : (
                  <Plus className="mr-2 h-4 w-4" aria-hidden="true" />
                )}
                New
              </Button>
            </div>
          </header>
          <div className="max-h-full overflow-y-auto p-2">
            {threads.length === 0 ? (
              <div className="rounded-md border border-border bg-muted/50 p-3 font-mono text-xs leading-5 text-muted-foreground">
                Start by typing a repo URL in chat.
              </div>
            ) : (
              threads.map((thread) => (
                <div
                  key={thread.threadId}
                  className={
                    thread.threadId === selectedThread?.threadId
                      ? "flex w-full items-start gap-2 rounded-md border border-primary bg-primary/10 p-3"
                      : "flex w-full items-start gap-2 rounded-md border border-transparent p-3 hover:border-border hover:bg-muted/50"
                  }
                >
                  <button
                    type="button"
                    className="min-w-0 flex-1 text-left"
                    onClick={() => {
                      onThreadChange(thread);
                      setActiveContext(contextFromThread(thread));
                      setIsNewThreadMode(false);
                    }}
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
                  <button
                    type="button"
                    className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-border bg-background text-muted-foreground hover:text-foreground disabled:opacity-50"
                    title={`Archive ${thread.title}`}
                    aria-label={`Archive ${thread.title}`}
                    disabled={archivingThreadId === thread.threadId || thread.status === "running"}
                    onClick={() => void archiveThread(thread)}
                  >
                    {archivingThreadId === thread.threadId ? (
                      <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                    ) : (
                      <Archive className="h-4 w-4" aria-hidden="true" />
                    )}
                  </button>
                </div>
              ))
            )}
          </div>
        </section>
      </aside>

      <section className="grid min-h-0 grid-rows-[auto_1fr_auto] overflow-hidden rounded-lg border border-border bg-card">
        <header className="border-b border-border bg-muted/60 px-4 py-3">
          <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant={threadStatusVariant(selectedThread?.status ?? "active")}>
                  {selectedThread?.status ?? "new"}
                </Badge>
                <Badge variant="outline">
                  {activeContext?.repoName ?? selectedThread?.repoName ?? "ambient chat"}
                </Badge>
              </div>
              <h2 className="mt-2 truncate font-mono text-lg font-semibold">
                {selectedThread?.title ?? "Wayfinder repo workspace"}
              </h2>
              <p className="mt-1 truncate font-mono text-xs text-muted-foreground">
                {activeContext?.repoUrl ?? "Attach a repo by typing Open https://github.com/owner/repo"}
              </p>
            </div>
            <Button
              type="button"
              variant="outline"
              disabled={selectedThread === null || isRefreshing}
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
          {activeRun !== null ? (
            <div className="mt-3 rounded-md border border-border bg-background p-3">
              <RunActivity status={activeRun.status} startedAt={activeRun.createdAt} />
            </div>
          ) : null}
        </header>

        <div className="min-h-0 overflow-y-auto px-4 py-4">
          <div className="mx-auto grid max-w-4xl gap-3">
            {!hasVisibleMessages ? (
              <div className="rounded-lg border border-dashed border-border bg-background p-6 font-mono text-sm leading-6 text-muted-foreground">
                Paste a repo URL, say `Use owner/repo`, or ask a repo question once a repo is active.
              </div>
            ) : (
              <>
                {selectedThread?.messages.map((message) => (
                  <ThreadMessageRow
                    key={message.messageId}
                    message={message}
                    linkedRun={runFromMessage(selectedThread.runs, message)}
                    onSelectRun={setSelectedAttachmentRun}
                  />
                ))}
                {pendingUserMessage !== null ? <PendingMessageRow content={pendingUserMessage} /> : null}
              </>
            )}

            {activeRun !== null ? (
              <details className="rounded-lg border border-border bg-background">
                <summary className="cursor-pointer px-4 py-3 font-mono text-sm font-semibold text-muted-foreground">
                  Grounded report
                </summary>
                <div className="border-t border-border p-2">
                  <CurrentRunConsole run={activeRun} source={source} embedded />
                </div>
              </details>
            ) : null}
          </div>
        </div>

        <div className="border-t border-border bg-muted/40 p-4">
          {error ? (
            <div className="mb-3 flex gap-2 rounded-md border border-danger/30 bg-danger/10 p-3 text-sm leading-6 text-danger">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
              <span>{error}</span>
            </div>
          ) : null}
          {statusMessage !== null && error === null ? (
            <div className="mb-3 flex gap-2 rounded-md border border-border bg-background p-3 text-sm leading-6 text-muted-foreground">
              {isSending ? (
                <Loader2 className="mt-0.5 h-4 w-4 shrink-0 animate-spin text-primary" aria-hidden="true" />
              ) : (
                <Bot className="mt-0.5 h-4 w-4 shrink-0 text-primary" aria-hidden="true" />
              )}
              <span>{statusMessage}</span>
            </div>
          ) : null}
          <form className="mx-auto grid max-w-4xl gap-2" onSubmit={sendChat}>
            <textarea
              className="min-h-24 resize-y rounded-md border border-border bg-background px-3 py-2 font-mono text-sm leading-6 text-foreground outline-none transition placeholder:text-muted-foreground focus:border-primary"
              value={chatDraft}
              onChange={(event) => setChatDraft(event.target.value)}
              onKeyDown={(event) => {
                if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
                  event.preventDefault();
                  event.currentTarget.form?.requestSubmit();
                }
              }}
              placeholder={
                activeContext?.repoUrl
                  ? "Ask naturally. Wayfinder will reuse the active repo context."
                  : "Open https://github.com/owner/repo or ask what repo to inspect."
              }
            />
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex flex-wrap items-center gap-2">
                {(["auto", "conversation", "report", "evidence"] as ChatAnswerMode[]).map((mode) => (
                  <button
                    key={mode}
                    type="button"
                    className={
                      answerMode === mode
                        ? "h-8 rounded-md bg-primary px-3 font-mono text-xs font-semibold text-primary-foreground"
                        : "h-8 rounded-md border border-border bg-background px-3 font-mono text-xs text-muted-foreground hover:text-foreground"
                    }
                    onClick={() => setAnswerMode(mode)}
                  >
                    {mode}
                  </button>
                ))}
              </div>
              <div className="flex items-center justify-between gap-3">
                <p className="font-mono text-[11px] leading-5 text-muted-foreground">
                  {sendBlocker ?? "Ambient repo context and bounded memory are attached."}
                </p>
                <Button type="submit" disabled={!canSend}>
                  {isSending ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />
                  ) : (
                    <Send className="mr-2 h-4 w-4" aria-hidden="true" />
                  )}
                  {isSending ? "Sending" : "Send"}
                </Button>
              </div>
            </div>
          </form>
        </div>
      </section>

      <aside className="grid min-h-0 grid-rows-[auto_1fr] gap-4">
        <ContextPanel context={activeContext} selectedRun={selectedAttachmentRun} />
        <AgentTracePanel trace={agentTrace} selectedRun={selectedAttachmentRun} />
      </aside>
    </section>
  );
}

function ThreadMessageRow({
  message,
  linkedRun,
  onSelectRun,
}: {
  message: DashboardThreadMessage;
  linkedRun: DashboardRun | null;
  onSelectRun: (run: DashboardRun | null) => void;
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
          <button type="button" onClick={() => onSelectRun(linkedRun)}>
            <Badge variant={runStatusVariant(linkedRun.status)}>run {linkedRun.status}</Badge>
          </button>
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

function PendingMessageRow({ content }: { content: string }) {
  return (
    <article className="ml-auto max-w-[86%] rounded-lg border border-primary/40 bg-primary/10 p-3 opacity-80">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <User className="h-4 w-4 text-primary" aria-hidden="true" />
        <span className="font-mono text-xs uppercase text-muted-foreground">user</span>
        <Badge variant="warning">sending</Badge>
      </div>
      <div className="whitespace-pre-wrap break-words font-mono text-sm leading-6 text-foreground">
        {content}
      </div>
    </article>
  );
}

function ContextPanel({
  context,
  selectedRun,
}: {
  context: ActiveRepoContext | null;
  selectedRun: DashboardRun | null;
}) {
  return (
    <section className="rounded-lg border border-border bg-card p-4">
      <div className="flex items-center gap-2 font-mono text-sm font-semibold">
        <PanelRight className="h-4 w-4 text-primary" aria-hidden="true" />
        Context
      </div>
      <div className="mt-3 grid gap-3 font-mono text-xs">
        <ContextRow label="repo" value={context?.repoName ?? "none"} />
        <ContextRow label="focus" value={context?.activeFocus ?? "none"} />
        <ContextRow label="thread" value={context?.defaultThreadId ?? "none"} />
        <ContextRow label="run" value={selectedRun?.jobId ?? context?.lastRunId ?? "none"} />
      </div>
      {context?.summaryMemory ? (
        <p className="mt-3 line-clamp-5 rounded-md border border-border bg-background p-3 font-mono text-[11px] leading-5 text-muted-foreground">
          {context.summaryMemory}
        </p>
      ) : null}
    </section>
  );
}

function AgentTracePanel({
  trace,
  selectedRun,
}: {
  trace: AgentTraceAttachment | null;
  selectedRun: DashboardRun | null;
}) {
  return (
    <section className="min-h-0 overflow-hidden rounded-lg border border-border bg-card">
      <header className="border-b border-border bg-muted/60 px-4 py-3">
        <div className="flex items-center gap-2 font-mono text-sm font-semibold">
          <BrainCircuit className="h-4 w-4 text-primary" aria-hidden="true" />
          Agent trace
        </div>
      </header>
      <div className="max-h-full overflow-y-auto p-4">
        {trace === null ? (
          <p className="font-mono text-xs leading-5 text-muted-foreground">
            Grounded chat responses will attach route, agents, tools, verifier status, and run evidence here.
          </p>
        ) : (
          <div className="grid gap-3">
            <div className="rounded-md border border-border bg-background p-3">
              <div className="flex flex-wrap gap-2">
                <Badge variant="outline">{trace.route.intent}</Badge>
                <Badge variant="outline">{trace.route.answerMode}</Badge>
                {trace.route.requiresGroundedRun ? <Badge variant="warning">grounded</Badge> : null}
              </div>
              <p className="mt-2 font-mono text-[11px] leading-5 text-muted-foreground">
                {trace.route.reason}
              </p>
            </div>
            {trace.steps.map((step) => (
              <div key={`${step.agentName}-${step.task}`} className="rounded-md border border-border p-3">
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate font-mono text-xs font-semibold">{step.agentName}</span>
                  <Badge variant={step.status === "completed" ? "success" : "outline"}>
                    {step.status}
                  </Badge>
                </div>
                <p className="mt-2 font-mono text-[11px] leading-5 text-muted-foreground">
                  {step.task}
                </p>
              </div>
            ))}
            {trace.toolRefs.length > 0 ? (
              <div className="flex flex-wrap gap-2">
                {trace.toolRefs.map((tool) => (
                  <Badge key={tool} variant="outline">
                    {tool}
                  </Badge>
                ))}
              </div>
            ) : null}
          </div>
        )}
        {selectedRun !== null ? (
          <div className="mt-4 rounded-md border border-border bg-background p-3">
            <div className="font-mono text-xs font-semibold">Selected run</div>
            <div className="mt-2 flex flex-wrap gap-2">
              <Badge variant={runStatusVariant(selectedRun.status)}>{selectedRun.status}</Badge>
              <Badge variant="success">verified {selectedRun.verifiedCount}</Badge>
              <Badge variant="warning">unverified {selectedRun.unverifiedCount}</Badge>
            </div>
          </div>
        ) : null}
      </div>
    </section>
  );
}

function ContextRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-3 rounded-md border border-border bg-background p-2">
      <span className="shrink-0 uppercase text-muted-foreground">{label}</span>
      <span className="min-w-0 break-all text-right text-foreground">{value}</span>
    </div>
  );
}

async function fetchThreadDetail(threadId: string): Promise<DashboardThread> {
  return postThread(`/api/wayfinder/threads/${encodeURIComponent(threadId)}`, undefined, "GET");
}

async function postChat(body: {
  content: string;
  thread_id: string | null;
  answer_mode: ChatAnswerMode;
}): Promise<ChatResponse> {
  const response = await fetch("/api/wayfinder/chat", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  const payload = await response.json().catch(() => null);

  if (!response.ok) {
    throw new Error(detailFromPayload(payload) ?? response.statusText);
  }

  return toChatResponse(payload as ApiChatResponse);
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

async function clearWorkspaceContext(): Promise<ActiveRepoContext> {
  const response = await fetch("/api/wayfinder/workspace/context", {
    method: "DELETE",
    headers: { "content-type": "application/json" },
  });
  const payload = await response.json().catch(() => null);

  if (!response.ok) {
    throw new Error(detailFromPayload(payload) ?? response.statusText);
  }

  return toActiveRepoContext(payload as ApiActiveRepoContext);
}

async function deleteThread(threadId: string): Promise<ActiveRepoContext> {
  const response = await fetch(`/api/wayfinder/threads/${encodeURIComponent(threadId)}`, {
    method: "DELETE",
    headers: { "content-type": "application/json" },
  });
  const payload = await response.json().catch(() => null);

  if (!response.ok) {
    throw new Error(detailFromPayload(payload) ?? response.statusText);
  }

  return toActiveRepoContext(payload as ApiActiveRepoContext);
}

function detailFromPayload(payload: unknown): string | null {
  if (payload !== null && typeof payload === "object") {
    const detail = (payload as { detail?: unknown }).detail;
    return typeof detail === "string" ? detail : null;
  }
  return null;
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Wayfinder chat request failed.";
}

function statusMessageFromChatResponse(response: ChatResponse): string {
  if (response.activeRun !== null) {
    return "Grounded repo run queued. The thread will refresh as evidence arrives.";
  }
  if (response.route.clarificationQuestion !== null) {
    return response.route.clarificationQuestion;
  }
  if (response.thread !== null) {
    return "Message sent. Active repo context is ready.";
  }
  return response.route.reason;
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

function contextFromThread(thread: DashboardThread | null): ActiveRepoContext | null {
  if (thread === null) {
    return null;
  }
  return {
    contextId: `thread:${thread.threadId}`,
    userId: thread.userId,
    repoUrl: thread.repoUrl,
    repoName: thread.repoName,
    defaultThreadId: thread.threadId,
    lastRunId: thread.lastRunId,
    status: thread.status === "running" ? "running" : thread.status === "failed" ? "failed" : "ready",
    summaryMemory: thread.summaryMemory,
    activeFocus: null,
    selectedFiles: [],
    selectedSymbols: [],
    limitations: [],
    updatedAt: thread.updatedAt,
  };
}

function sendDisabledReason({
  draft,
  selectedThread,
  isSending,
  hasActiveRepo,
}: {
  draft: string;
  selectedThread: DashboardThread | null;
  isSending: boolean;
  hasActiveRepo: boolean;
}): string | null {
  if (isSending) {
    return "sending";
  }
  if (draft.trim().length === 0) {
    return "message is empty";
  }
  // No repo to ground against: only allow messages that attach one (URL / owner/repo),
  // so a plain question is not silently sent and cleared with no answer.
  if (!hasActiveRepo && selectedThread === null && !containsRepoReference(draft)) {
    return "open a repo first";
  }
  if (selectedThread?.status === "running" && !containsRepoReference(draft)) {
    return "run in progress";
  }
  return null;
}

function containsRepoReference(content: string): boolean {
  return (
    /https:\/\/github\.com\/[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+\/?/.test(content) ||
    /\b[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+\b/.test(content)
  );
}

function threadStatusVariant(
  status: ThreadStatus | "new",
): "success" | "warning" | "danger" | "outline" {
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

function contextStatusVariant(
  status: ActiveRepoContext["status"],
): "success" | "warning" | "danger" | "outline" {
  if (status === "ready") {
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
