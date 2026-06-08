import { toDashboardRun } from "@/lib/metrics";
import type {
  ApiConversationThreadDetail,
  ApiThreadMessage,
  DashboardThread,
  DashboardThreadMessage,
} from "@/lib/types";

export function toDashboardThread(detail: ApiConversationThreadDetail): DashboardThread {
  return {
    threadId: detail.thread.thread_id,
    userId: detail.thread.user_id,
    repoUrl: detail.thread.repo_url,
    repoName: detail.thread.repo_name,
    title: detail.thread.title,
    status: detail.thread.status,
    createdAt: detail.thread.created_at,
    updatedAt: detail.thread.updated_at,
    lastRunId: detail.thread.last_run_id,
    summaryMemory: detail.thread.summary_memory,
    messages: detail.messages.map(toDashboardThreadMessage),
    runs: detail.runs.map(toDashboardRun),
    activeRun: detail.active_run ? toDashboardRun(detail.active_run) : null,
  };
}

export function upsertThread(
  threads: DashboardThread[],
  nextThread: DashboardThread,
): DashboardThread[] {
  const withoutThread = threads.filter((thread) => thread.threadId !== nextThread.threadId);
  return [nextThread, ...withoutThread].sort(
    (a, b) => timestamp(b.updatedAt) - timestamp(a.updatedAt),
  );
}

function toDashboardThreadMessage(message: ApiThreadMessage): DashboardThreadMessage {
  return {
    messageId: message.message_id,
    threadId: message.thread_id,
    role: message.role,
    content: message.content,
    createdAt: message.created_at,
    sourceRunId: message.source_run_id,
    evidenceRefs: message.evidence_refs,
    verifiedCount: message.verified_count,
    unverifiedCount: message.unverified_count,
    contradictedCount: message.contradicted_count,
    traceMetadata: message.trace_metadata ?? {},
  };
}

function timestamp(value: string): number {
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : 0;
}
