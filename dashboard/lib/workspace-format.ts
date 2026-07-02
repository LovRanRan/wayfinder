import type {
  ActiveRepoContext,
  ChatResponse,
  DashboardThread,
  RunStatus,
  ThreadStatus,
} from "@/lib/types";

export function threadStatusVariant(
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

export function contextStatusVariant(
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

export function runStatusVariant(status: RunStatus): "success" | "warning" | "danger" | "outline" {
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

export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Wayfinder chat request failed.";
}

export function statusMessageFromChatResponse(response: ChatResponse): string {
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

export function threadFromId(
  threads: DashboardThread[],
  threadId: string | null,
): DashboardThread | null {
  if (threadId === null) {
    return null;
  }
  return threads.find((thread) => thread.threadId === threadId) ?? null;
}

export function contextFromThread(thread: DashboardThread | null): ActiveRepoContext | null {
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

export function sendDisabledReason({
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
  if (selectedThread?.status === "archived") {
    return "thread archived (read-only)";
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
