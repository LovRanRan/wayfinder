export type RunStatus = "queued" | "running" | "completed" | "failed";

export type RunIntent = "architectural" | "runtime" | "behavioral" | "debug" | "mixed";

export type TraceMetadataValue = string | number | boolean | null;
export type WorkspaceLLMRouting = "off" | "openai";
export type WorkspaceFinalWriter = "deterministic" | "openai";
export type WorkspaceSandboxStatus = "disabled" | "unavailable" | "enabled";

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

export type DashboardMetrics = {
  totalRuns: number;
  activeRuns: number;
  verifiedClaims: number;
  unverifiedClaims: number;
  contradictedClaims: number;
  verificationRate: number;
  p50Latency: number;
  p95Latency: number;
  totalTokens: number;
  totalCostUsd: number;
};
