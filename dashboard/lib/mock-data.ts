import type { RunSummary } from "@/lib/types";

export const mockRuns: RunSummary[] = [
  {
    jobId: "run_langchain_bootstrap",
    repoName: "langchain-ai/langchain",
    repoUrl: "https://github.com/langchain-ai/langchain",
    intent: "mixed",
    status: "completed",
    verifiedCount: 0,
    unverifiedCount: 0,
    contradictedCount: 0,
    traceUrl: "https://smith.langchain.com/",
  },
  {
    jobId: "run_fixture_architecture",
    repoName: "fixture/python-service",
    repoUrl: "local://fixture/python-service",
    intent: "architectural",
    status: "running",
    verifiedCount: 2,
    unverifiedCount: 1,
    contradictedCount: 0,
    traceUrl: "https://smith.langchain.com/",
  },
];
