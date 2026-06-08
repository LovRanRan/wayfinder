import { NextRequest, NextResponse } from "next/server";

import { proxyWayfinderJson } from "@/lib/wayfinder-proxy";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  const limit = request.nextUrl.searchParams.get("limit") ?? "20";
  return proxyWayfinderJson(`/threads?limit=${encodeURIComponent(limit)}`);
}

export async function POST(request: NextRequest) {
  const payload = await request.json().catch(() => null);

  if (!isThreadCreatePayload(payload)) {
    return NextResponse.json(
      { detail: "repo_url and optional initial_query are required." },
      { status: 400 },
    );
  }

  return proxyWayfinderJson("/threads", {
    method: "POST",
    body: {
      repo_url: payload.repo_url.trim(),
      title: payload.title?.trim() || undefined,
      initial_query: payload.initial_query?.trim() || undefined,
    },
  });
}

function isThreadCreatePayload(
  payload: unknown,
): payload is { repo_url: string; title?: string; initial_query?: string } {
  if (payload === null || typeof payload !== "object") {
    return false;
  }

  const candidate = payload as Record<string, unknown>;
  return (
    typeof candidate.repo_url === "string" &&
    candidate.repo_url.trim().length > 0 &&
    optionalString(candidate.title) &&
    optionalString(candidate.initial_query)
  );
}

function optionalString(value: unknown): boolean {
  return value === undefined || typeof value === "string";
}
