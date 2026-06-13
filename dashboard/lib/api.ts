import { mockRuns } from "@/lib/mock-data";
import { toDashboardRun } from "@/lib/metrics";
import { authorizationHeader, sessionTokenFromCookies } from "@/lib/session";
import { toDashboardThread } from "@/lib/threads";
import type {
  ApiConversationThreadDetail,
  ApiRunSummary,
  ApiUserProfile,
  DashboardRun,
  DashboardThread,
  DashboardUser,
} from "@/lib/types";

export type DashboardData = {
  runs: DashboardRun[];
  threads: DashboardThread[];
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
      return { runs: [], threads: [], user: null, source: "api", apiBaseUrl, publicApiBaseUrl };
    }

    if (!meResponse.ok) {
      return {
        runs: mockRuns,
        threads: [],
        user: null,
        source: "demo",
        apiBaseUrl,
        publicApiBaseUrl,
      };
    }

    const user = toDashboardUser((await meResponse.json()) as ApiUserProfile);
    const [runsResponse, threadsResponse] = await Promise.all([
      fetch(`${apiBaseUrl}/runs?limit=10`, {
        headers: authHeaders,
        cache: "no-store",
      }),
      fetch(`${apiBaseUrl}/threads?limit=20&include_archived=true`, {
        headers: authHeaders,
        cache: "no-store",
      }),
    ]);

    if (!runsResponse.ok) {
      return {
        runs: mockRuns,
        threads: [],
        user,
        source: "demo",
        apiBaseUrl,
        publicApiBaseUrl,
      };
    }

    const runs = (await runsResponse.json()) as ApiRunSummary[];
    const threads = threadsResponse.ok
      ? ((await threadsResponse.json()) as ApiConversationThreadDetail[])
      : [];
    return {
      runs: runs.map(toDashboardRun),
      threads: threads.map(toDashboardThread),
      user,
      source: "api",
      apiBaseUrl,
      publicApiBaseUrl,
    };
  } catch {
    return {
      runs: mockRuns,
      threads: [],
      user: null,
      source: "demo",
      apiBaseUrl,
      publicApiBaseUrl,
    };
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
