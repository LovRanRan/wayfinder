import { NextRequest, NextResponse } from "next/server";

import { proxyWayfinderJson } from "@/lib/wayfinder-proxy";

export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  const payload = await request.json().catch(() => null);

  if (!isChatPayload(payload)) {
    return NextResponse.json({ detail: "content is required." }, { status: 400 });
  }

  return proxyWayfinderJson("/chat", {
    method: "POST",
    body: {
      content: payload.content.trim(),
      thread_id: stringOrNull(payload.thread_id),
      repo_url: stringOrNull(payload.repo_url),
      answer_mode: stringOrDefault(payload.answer_mode, "auto"),
    },
  });
}

function isChatPayload(payload: unknown): payload is Record<string, unknown> & { content: string } {
  if (payload === null || typeof payload !== "object") {
    return false;
  }
  const candidate = payload as Record<string, unknown>;
  return typeof candidate.content === "string" && candidate.content.trim().length > 0;
}

function stringOrNull(value: unknown): string | null {
  return typeof value === "string" && value.trim().length > 0 ? value.trim() : null;
}

function stringOrDefault(value: unknown, fallback: string): string {
  return typeof value === "string" && value.trim().length > 0 ? value.trim() : fallback;
}
