export type RunStatus = "queued" | "running" | "completed" | "failed";

export type RunIntent = "architectural" | "runtime" | "behavioral" | "debug" | "mixed";

export type RunSummary = {
  jobId: string;
  repoName: string;
  repoUrl: string;
  intent: RunIntent;
  status: RunStatus;
  verifiedCount: number;
  unverifiedCount: number;
  contradictedCount: number;
  traceUrl: string;
};
