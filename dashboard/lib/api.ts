import { mockRuns } from "@/lib/mock-data";
import { toDashboardRun } from "@/lib/metrics";
import type { ApiRunSummary, DashboardRun } from "@/lib/types";

export type DashboardData = {
  runs: DashboardRun[];
  source: "api" | "demo";
  apiBaseUrl: string;
};

export async function getDashboardData(): Promise<DashboardData> {
  const apiBaseUrl = apiBaseUrlFromEnv();

  try {
    const response = await fetch(`${apiBaseUrl}/runs?limit=10`, {
      cache: "no-store",
    });

    if (!response.ok) {
      return { runs: mockRuns, source: "demo", apiBaseUrl };
    }

    const runs = (await response.json()) as ApiRunSummary[];
    if (runs.length === 0) {
      return { runs: mockRuns, source: "demo", apiBaseUrl };
    }

    return { runs: runs.map(toDashboardRun), source: "api", apiBaseUrl };
  } catch {
    return { runs: mockRuns, source: "demo", apiBaseUrl };
  }
}

function apiBaseUrlFromEnv(): string {
  return (
    process.env.WAYFINDER_API_BASE_URL ??
    process.env.NEXT_PUBLIC_WAYFINDER_API_BASE_URL ??
    "http://localhost:8000"
  ).replace(/\/$/, "");
}
