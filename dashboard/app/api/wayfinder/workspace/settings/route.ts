import { NextRequest, NextResponse } from "next/server";

import { proxyWayfinderJson } from "@/lib/wayfinder-proxy";

export const dynamic = "force-dynamic";

export async function GET() {
  return proxyWayfinderJson("/workspace/settings");
}

export async function PUT(request: NextRequest) {
  const payload = await request.json().catch(() => null);
  if (!isSettingsPayload(payload)) {
    return NextResponse.json({ detail: "Invalid workspace settings payload." }, { status: 400 });
  }

  return proxyWayfinderJson("/workspace/settings", {
    method: "PUT",
    body: payload,
  });
}

function isSettingsPayload(payload: unknown): payload is Record<string, unknown> {
  return payload !== null && typeof payload === "object" && !Array.isArray(payload);
}
