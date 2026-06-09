import { toDashboardRun } from "@/lib/metrics";
import { toDashboardThread } from "@/lib/threads";
import type {
  ActiveRepoContext,
  AgentTraceAttachment,
  ApiActiveRepoContext,
  ApiAgentTraceAttachment,
  ApiChatResponse,
  ApiChatRouteDecision,
  ChatResponse,
  ChatRouteDecision,
} from "@/lib/types";

export function toChatResponse(payload: ApiChatResponse): ChatResponse {
  return {
    thread: payload.thread === null ? null : toDashboardThread(payload.thread),
    activeContext: toActiveRepoContext(payload.active_context),
    activeRun: payload.active_run === null ? null : toDashboardRun(payload.active_run),
    route: toChatRouteDecision(payload.route),
    agentTrace: toAgentTraceAttachment(payload.agent_trace),
  };
}

export function toActiveRepoContext(payload: ApiActiveRepoContext): ActiveRepoContext {
  return {
    contextId: payload.context_id,
    userId: payload.user_id,
    repoUrl: payload.repo_url,
    repoName: payload.repo_name,
    defaultThreadId: payload.default_thread_id,
    lastRunId: payload.last_run_id,
    status: payload.status,
    summaryMemory: payload.summary_memory,
    activeFocus: payload.active_focus,
    selectedFiles: payload.selected_files,
    selectedSymbols: payload.selected_symbols,
    limitations: payload.limitations,
    updatedAt: payload.updated_at,
  };
}

function toChatRouteDecision(payload: ApiChatRouteDecision): ChatRouteDecision {
  return {
    intent: payload.intent,
    answerMode: payload.answer_mode,
    requiresGroundedRun: payload.requires_grounded_run,
    requiresContextSwitch: payload.requires_context_switch,
    clarificationQuestion: payload.clarification_question,
    activeFocus: payload.active_focus,
    reason: payload.reason,
  };
}

function toAgentTraceAttachment(payload: ApiAgentTraceAttachment): AgentTraceAttachment {
  return {
    route: toChatRouteDecision(payload.route),
    steps: payload.steps.map((step) => ({
      agentName: step.agent_name,
      task: step.task,
      status: step.status,
      evidenceRefs: step.evidence_refs,
      limitations: step.limitations,
    })),
    toolRefs: payload.tool_refs,
    verifierStatus: payload.verifier_status,
    finalHandoff: payload.final_handoff,
  };
}
