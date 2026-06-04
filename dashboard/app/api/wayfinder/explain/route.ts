import { NextRequest, NextResponse } from "next/server";

import { proxyWayfinderJson } from "@/lib/wayfinder-proxy";

export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  const payload = await request.json().catch(() => null);

  if (!isExplainPayload(payload)) {
    return NextResponse.json({ detail: "repo_url and query are required." }, { status: 400 });
  }

  return proxyWayfinderJson("/explain", {
    method: "POST",
    body: {
      repo_url: payload.repo_url.trim(),
      query: payload.query.trim(),
    },
  });
}

function isExplainPayload(payload: unknown): payload is { repo_url: string; query: string } {
  if (payload === null || typeof payload !== "object") {
    return false;
  }

  const candidate = payload as Record<string, unknown>;
  return (
    typeof candidate.repo_url === "string" &&
    candidate.repo_url.trim().length > 0 &&
    typeof candidate.query === "string" &&
    candidate.query.trim().length > 0
  );
}
