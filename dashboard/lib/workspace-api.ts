import { toActiveRepoContext, toChatResponse } from "@/lib/chat";
import { toDashboardThread } from "@/lib/threads";
import type {
  ActiveRepoContext,
  ApiActiveRepoContext,
  ApiChatResponse,
  ApiConversationThreadDetail,
  ChatAnswerMode,
  ChatResponse,
  DashboardThread,
} from "@/lib/types";

export async function fetchThreadDetail(threadId: string): Promise<DashboardThread> {
  return postThread(`/api/wayfinder/threads/${encodeURIComponent(threadId)}`, undefined, "GET");
}

export async function postChat(body: {
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

export async function clearWorkspaceContext(): Promise<ActiveRepoContext> {
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

export async function deleteThread(threadId: string): Promise<ActiveRepoContext> {
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
