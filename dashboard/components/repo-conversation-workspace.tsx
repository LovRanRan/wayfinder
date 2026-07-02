"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

import { ChatPanel } from "@/components/workspace/chat-panel";
import { ContextRail } from "@/components/workspace/context-rail";
import { ThreadRail } from "@/components/workspace/thread-rail";
import { upsertThread } from "@/lib/threads";
import {
  clearWorkspaceContext,
  deleteThread,
  fetchThreadDetail,
  postChat,
} from "@/lib/workspace-api";
import {
  contextFromThread,
  errorMessage,
  sendDisabledReason,
  statusMessageFromChatResponse,
  threadFromId,
} from "@/lib/workspace-format";
import type {
  ActiveRepoContext,
  AgentTraceAttachment,
  ChatAnswerMode,
  DashboardRun,
  DashboardThread,
  RunStatus,
} from "@/lib/types";

const activeRunStatuses: RunStatus[] = ["queued", "running"];

type RepoConversationWorkspaceProps = {
  threads: DashboardThread[];
  selectedThreadId: string | null;
  source: "api" | "demo";
  externalRun?: DashboardRun | null;
  onNewThread: () => void;
  onThreadChange: (thread: DashboardThread) => void;
  onThreadArchived: (threadId: string) => void;
  onRunChange: (run: DashboardRun | null) => void;
};

export function RepoConversationWorkspace({
  threads,
  selectedThreadId,
  source,
  externalRun = null,
  onNewThread,
  onThreadChange,
  onThreadArchived,
  onRunChange,
}: RepoConversationWorkspaceProps) {
  const [isNewThreadMode, setIsNewThreadMode] = useState(false);
  // A thread opened from History that is not in the active prop list (e.g.
  // archived) is fetched on demand so it can still be displayed read-only.
  const [loadedThread, setLoadedThread] = useState<DashboardThread | null>(null);
  // Archived threads stay loadable (so History can open them read-only) but are
  // hidden from the active thread rail / default selection.
  const activeThreads = useMemo(
    () => threads.filter((thread) => thread.status !== "archived"),
    [threads],
  );
  const selectedThread = useMemo(() => {
    if (selectedThreadId === null && isNewThreadMode) {
      return null;
    }
    return (
      threadFromId(threads, selectedThreadId) ??
      (loadedThread?.threadId === selectedThreadId ? loadedThread : null) ??
      activeThreads[0] ??
      null
    );
  }, [isNewThreadMode, selectedThreadId, threads, activeThreads, loadedThread]);

  useEffect(() => {
    if (selectedThreadId === null) {
      return;
    }
    if (threadFromId(threads, selectedThreadId) !== null) {
      return;
    }
    if (loadedThread?.threadId === selectedThreadId) {
      return;
    }
    let cancelled = false;
    void fetchThreadDetail(selectedThreadId)
      .then((thread) => {
        if (!cancelled) {
          setLoadedThread(thread);
        }
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [selectedThreadId, threads, loadedThread]);
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
  const activeRun = selectedAttachmentRun ?? selectedThread?.activeRun ?? null;
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
      // Switch the active context when the selected thread changes identity
      // (e.g. opening a different/archived thread from History). Keep the
      // existing context only when it already belongs to this same thread, so a
      // rich chat-returned context isn't clobbered on in-thread re-renders.
      setActiveContext((current) =>
        current?.defaultThreadId === selectedThread.threadId
          ? current
          : contextFromThread(selectedThread),
      );
      setSelectedAttachmentRun(selectedThread.activeRun);
    }
  }, [selectedThread]);

  // A run picked from History (or a just-completed chat run) is an explicit
  // selection — surface its report even if it belongs to a different repo/thread
  // than the default. Feeds the attachment-run that drives the Grounded report.
  useEffect(() => {
    if (externalRun !== null) {
      setSelectedAttachmentRun(externalRun);
    }
  }, [externalRun]);

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

  async function submitChatContent(nextContent: string) {
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

  async function sendChat(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canSend) {
      return;
    }
    await submitChatContent(chatDraft.trim());
  }

  async function attachRepo(repoRef: string) {
    const trimmed = repoRef.trim();
    if (trimmed === "" || isSending) {
      return;
    }
    // Reuse the chat routing that already understands "Open <repo>" so the
    // dedicated input and the typed command take the identical backend path.
    await submitChatContent(`Open ${trimmed}`);
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
      <ThreadRail
        activeContext={activeContext}
        activeThreads={activeThreads}
        selectedThreadId={selectedThread?.threadId ?? null}
        isClearingContext={isClearingContext}
        archivingThreadId={archivingThreadId}
        isAttachingRepo={isSending}
        onAttachRepo={(repoRef) => void attachRepo(repoRef)}
        onStartNewThread={() => void startNewThread()}
        onSelectThread={(thread) => {
          onThreadChange(thread);
          setActiveContext(contextFromThread(thread));
          setIsNewThreadMode(false);
        }}
        onArchiveThread={(thread) => void archiveThread(thread)}
      />

      <ChatPanel
        selectedThread={selectedThread}
        activeContext={activeContext}
        activeRun={activeRun}
        source={source}
        hasVisibleMessages={hasVisibleMessages}
        pendingUserMessage={pendingUserMessage}
        error={error}
        statusMessage={statusMessage}
        chatDraft={chatDraft}
        answerMode={answerMode}
        sendBlocker={sendBlocker}
        canSend={canSend}
        isSending={isSending}
        isRefreshing={isRefreshing}
        onChatDraftChange={setChatDraft}
        onAnswerModeChange={setAnswerMode}
        onSendChat={sendChat}
        onRefreshThread={() => void refreshSelectedThread()}
        onSelectRun={setSelectedAttachmentRun}
      />

      <ContextRail
        context={activeContext}
        trace={agentTrace}
        selectedRun={selectedAttachmentRun}
      />
    </section>
  );
}

export function mergeThreadList(
  threads: DashboardThread[],
  nextThread: DashboardThread,
): DashboardThread[] {
  return upsertThread(threads, nextThread);
}
