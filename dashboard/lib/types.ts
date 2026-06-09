export type RunStatus = "queued" | "running" | "completed" | "failed";
export type ThreadStatus = "active" | "running" | "failed" | "archived";
export type ThreadMessageRole = "user" | "assistant" | "system";

export type RunIntent = "architectural" | "runtime" | "behavioral" | "debug" | "mixed";

export type TraceMetadataValue = string | number | boolean | null;
export type WorkspaceLLMRouting = "off" | "openai";
export type WorkspaceFinalWriter = "deterministic" | "openai";
export type WorkspaceSandboxStatus = "disabled" | "unavailable" | "enabled";
export type ChatAnswerMode = "auto" | "conversation" | "report" | "evidence" | "clarify";
export type ChatIntent =
  | "chat_only"
  | "repo_question"
  | "context_switch"
  | "structured_report"
  | "evidence_request"
  | "clarification"
  | "unsupported_action";
export type AgentTraceRole =
  | "conversation_memory_agent"
  | "supervisor_agent"
  | "repo_cartographer_agent"
  | "symbol_investigator_agent"
  | "verification_agent"
  | "final_synthesizer_agent"
  | "external_context_scout";

export type DashboardUser = {
  userId: string;
  workspaceId: string;
  displayName: string;
};

export type ApiUserProfile = {
  user_id: string;
  workspace_id: string;
  display_name: string;
};

export type ApiWorkspaceSettings = {
  workspace_id: string;
  display_name: string;
  openai_key_configured: boolean;
  openai_key_label: string | null;
  openai_model: string;
  llm_routing: WorkspaceLLMRouting;
  final_writer: WorkspaceFinalWriter;
  verifier_runner: string;
  sandbox_status: WorkspaceSandboxStatus;
  sandbox_message: string;
};

export type WorkspaceSettings = {
  workspaceId: string;
  displayName: string;
  openaiKeyConfigured: boolean;
  openaiKeyLabel: string | null;
  openaiModel: string;
  llmRouting: WorkspaceLLMRouting;
  finalWriter: WorkspaceFinalWriter;
  verifierRunner: string;
  sandboxStatus: WorkspaceSandboxStatus;
  sandboxMessage: string;
};

export type RunError = {
  node: string;
  errorType: string;
  message: string;
  retryable: boolean;
};

export type ApiRunError = {
  node: string;
  error_type: string;
  message: string;
  retryable: boolean;
};

export type ApiRunSummary = {
  job_id: string;
  user_id: string;
  repo_url: string;
  query: string;
  status: RunStatus;
  current_node: string | null;
  final_output: string | null;
  error: string | null;
  partial_summaries: Record<string, string>;
  errors: ApiRunError[];
  user_corrections: string[];
  verified_count: number;
  unverified_count: number;
  contradicted_count: number;
  trace_url: string | null;
  trace_metadata: Record<string, TraceMetadataValue>;
  created_at: string;
  updated_at: string;
};

export type ApiThreadMessage = {
  message_id: string;
  thread_id: string;
  role: ThreadMessageRole;
  content: string;
  created_at: string;
  source_run_id: string | null;
  evidence_refs: string[];
  verified_count: number;
  unverified_count: number;
  contradicted_count: number;
  trace_metadata: Record<string, TraceMetadataValue>;
};

export type ApiConversationThread = {
  thread_id: string;
  user_id: string;
  repo_url: string;
  repo_name: string;
  title: string;
  status: ThreadStatus;
  created_at: string;
  updated_at: string;
  last_run_id: string | null;
  summary_memory: string | null;
};

export type ApiConversationThreadDetail = {
  thread: ApiConversationThread;
  messages: ApiThreadMessage[];
  runs: ApiRunSummary[];
  active_run: ApiRunSummary | null;
};

export type ApiActiveRepoContext = {
  context_id: string;
  user_id: string;
  repo_url: string | null;
  repo_name: string | null;
  default_thread_id: string | null;
  last_run_id: string | null;
  status: "empty" | "ready" | "running" | "failed";
  summary_memory: string | null;
  active_focus: string | null;
  selected_files: string[];
  selected_symbols: string[];
  limitations: string[];
  updated_at: string;
};

export type ApiChatRouteDecision = {
  intent: ChatIntent;
  answer_mode: ChatAnswerMode;
  requires_grounded_run: boolean;
  requires_context_switch: boolean;
  clarification_question: string | null;
  active_focus: string | null;
  reason: string;
};

export type ApiAgentTraceStep = {
  agent_name: AgentTraceRole;
  task: string;
  status: "planned" | "queued" | "completed" | "skipped";
  evidence_refs: string[];
  limitations: string[];
};

export type ApiAgentTraceAttachment = {
  route: ApiChatRouteDecision;
  steps: ApiAgentTraceStep[];
  tool_refs: string[];
  verifier_status: string | null;
  final_handoff: string | null;
};

export type ApiChatResponse = {
  thread: ApiConversationThreadDetail | null;
  active_context: ApiActiveRepoContext;
  active_run: ApiRunSummary | null;
  route: ApiChatRouteDecision;
  agent_trace: ApiAgentTraceAttachment;
};

export type DashboardRun = {
  jobId: string;
  userId: string;
  repoName: string;
  repoUrl: string;
  query: string;
  intent: RunIntent;
  status: RunStatus;
  currentNode: string | null;
  finalOutput: string | null;
  error: string | null;
  partialSummaries: Record<string, string>;
  errors: RunError[];
  userCorrections: string[];
  verifiedCount: number;
  unverifiedCount: number;
  contradictedCount: number;
  traceUrl: string | null;
  traceMetadata: Record<string, TraceMetadataValue>;
  agentName: string;
  toolName: string | null;
  mcpServer: string | null;
  latency: number;
  tokens: number;
  costUsd: number;
  failureModes: string[];
  createdAt: string;
  updatedAt: string;
};

export type DashboardThreadMessage = {
  messageId: string;
  threadId: string;
  role: ThreadMessageRole;
  content: string;
  createdAt: string;
  sourceRunId: string | null;
  evidenceRefs: string[];
  verifiedCount: number;
  unverifiedCount: number;
  contradictedCount: number;
  traceMetadata: Record<string, TraceMetadataValue>;
};

export type DashboardThread = {
  threadId: string;
  userId: string;
  repoUrl: string;
  repoName: string;
  title: string;
  status: ThreadStatus;
  createdAt: string;
  updatedAt: string;
  lastRunId: string | null;
  summaryMemory: string | null;
  messages: DashboardThreadMessage[];
  runs: DashboardRun[];
  activeRun: DashboardRun | null;
};

export type ActiveRepoContext = {
  contextId: string;
  userId: string;
  repoUrl: string | null;
  repoName: string | null;
  defaultThreadId: string | null;
  lastRunId: string | null;
  status: "empty" | "ready" | "running" | "failed";
  summaryMemory: string | null;
  activeFocus: string | null;
  selectedFiles: string[];
  selectedSymbols: string[];
  limitations: string[];
  updatedAt: string;
};

export type ChatRouteDecision = {
  intent: ChatIntent;
  answerMode: ChatAnswerMode;
  requiresGroundedRun: boolean;
  requiresContextSwitch: boolean;
  clarificationQuestion: string | null;
  activeFocus: string | null;
  reason: string;
};

export type AgentTraceStep = {
  agentName: AgentTraceRole;
  task: string;
  status: "planned" | "queued" | "completed" | "skipped";
  evidenceRefs: string[];
  limitations: string[];
};

export type AgentTraceAttachment = {
  route: ChatRouteDecision;
  steps: AgentTraceStep[];
  toolRefs: string[];
  verifierStatus: string | null;
  finalHandoff: string | null;
};

export type ChatResponse = {
  thread: DashboardThread | null;
  activeContext: ActiveRepoContext;
  activeRun: DashboardRun | null;
  route: ChatRouteDecision;
  agentTrace: AgentTraceAttachment;
};

export type DashboardMetrics = {
  totalRuns: number;
  activeRuns: number;
  completedRuns: number;
  failedRuns: number;
  terminalRuns: number;
  successRate: number;
  verifiedClaims: number;
  unverifiedClaims: number;
  contradictedClaims: number;
  verificationRate: number;
  latestCompletedLatency: number;
  completedLatencySamples: number;
  p50Latency: number;
  p95Latency: number;
  totalTokens: number;
  totalCostUsd: number;
};
