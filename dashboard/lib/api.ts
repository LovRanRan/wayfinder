import { mockRuns } from "@/lib/mock-data";
import { toDashboardRun } from "@/lib/metrics";
import { authorizationHeader, sessionTokenFromCookies } from "@/lib/session";
import type { ApiRunSummary, ApiUserProfile, DashboardRun, DashboardUser } from "@/lib/types";

export type DashboardData = {
  runs: DashboardRun[];
  user: DashboardUser | null;
  source: "api" | "demo";
  apiBaseUrl: string;
  publicApiBaseUrl: string;
};

export async function getDashboardData(): Promise<DashboardData> {
  const apiBaseUrl = apiBaseUrlFromEnv();
  const publicApiBaseUrl = publicApiBaseUrlFromEnv(apiBaseUrl);
  const token = await sessionTokenFromCookies();
  const authHeaders = authorizationHeader(token);

  try {
    const meResponse = await fetch(`${apiBaseUrl}/auth/me`, {
      headers: authHeaders,
      cache: "no-store",
    });

    if (meResponse.status === 401) {
      return { runs: [], user: null, source: "api", apiBaseUrl, publicApiBaseUrl };
    }

    if (!meResponse.ok) {
      return { runs: mockRuns, user: null, source: "demo", apiBaseUrl, publicApiBaseUrl };
    }

    const user = toDashboardUser((await meResponse.json()) as ApiUserProfile);
    const response = await fetch(`${apiBaseUrl}/runs?limit=10`, {
      headers: authHeaders,
      cache: "no-store",
    });

    if (!response.ok) {
      return { runs: mockRuns, user, source: "demo", apiBaseUrl, publicApiBaseUrl };
    }

    const runs = (await response.json()) as ApiRunSummary[];
    return { runs: runs.map(toDashboardRun), user, source: "api", apiBaseUrl, publicApiBaseUrl };
  } catch {
    return { runs: mockRuns, user: null, source: "demo", apiBaseUrl, publicApiBaseUrl };
  }
}

function toDashboardUser(user: ApiUserProfile): DashboardUser {
  return {
    userId: user.user_id,
    workspaceId: user.workspace_id,
    displayName: user.display_name,
  };
}

export function apiBaseUrlFromEnv(): string {
  return (
    process.env.WAYFINDER_API_BASE_URL ??
    process.env.NEXT_PUBLIC_WAYFINDER_API_BASE_URL ??
    "http://localhost:8000"
  ).replace(/\/$/, "");
}

export function publicApiBaseUrlFromEnv(apiBaseUrl = apiBaseUrlFromEnv()): string {
  return (
    process.env.NEXT_PUBLIC_WAYFINDER_API_BASE_URL ??
    process.env.WAYFINDER_PUBLIC_API_BASE_URL ??
    apiBaseUrl
  ).replace(/\/$/, "");
}
