import { NextRequest, NextResponse } from "next/server";

import { proxyWayfinderJson } from "@/lib/wayfinder-proxy";

export const dynamic = "force-dynamic";

type RouteContext = {
  params: Promise<{ jobId: string }>;
};

export async function POST(request: NextRequest, context: RouteContext) {
  const payload = await request.json().catch(() => null);

  if (!isRefinePayload(payload)) {
    return NextResponse.json({ detail: "correction is required." }, { status: 400 });
  }

  const { jobId } = await context.params;
  return proxyWayfinderJson(`/refine/${encodeURIComponent(jobId)}`, {
    method: "POST",
    body: { correction: payload.correction.trim() },
  });
}

function isRefinePayload(payload: unknown): payload is { correction: string } {
  if (payload === null || typeof payload !== "object") {
    return false;
  }

  const candidate = payload as Record<string, unknown>;
  return typeof candidate.correction === "string" && candidate.correction.trim().length > 0;
}
