import { NextRequest, NextResponse } from "next/server";

import { proxyWayfinderJson } from "@/lib/wayfinder-proxy";

export const dynamic = "force-dynamic";

type RouteParams = {
  params: Promise<{ threadId: string }>;
};

export async function POST(request: NextRequest, { params }: RouteParams) {
  const payload = await request.json().catch(() => null);
  const { threadId } = await params;

  if (!isMessagePayload(payload)) {
    return NextResponse.json({ detail: "content is required." }, { status: 400 });
  }

  return proxyWayfinderJson(`/threads/${encodeURIComponent(threadId)}/messages`, {
    method: "POST",
    body: {
      content: payload.content.trim(),
    },
  });
}

function isMessagePayload(payload: unknown): payload is { content: string } {
  if (payload === null || typeof payload !== "object") {
    return false;
  }

  const candidate = payload as Record<string, unknown>;
  return typeof candidate.content === "string" && candidate.content.trim().length > 0;
}
