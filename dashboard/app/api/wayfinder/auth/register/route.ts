import { NextRequest, NextResponse } from "next/server";

import { apiBaseUrlFromEnv } from "@/lib/api";
import { SESSION_COOKIE } from "@/lib/session";

export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  const payload = await request.json().catch(() => null);
  if (!isAuthPayload(payload)) {
    return NextResponse.json(
      { detail: "workspace_id, display_name, and password are required." },
      { status: 400 },
    );
  }

  const response = await fetch(`${apiBaseUrlFromEnv()}/auth/register`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      workspace_id: payload.workspace_id.trim(),
      password: payload.password,
      display_name: payload.display_name.trim(),
    }),
    cache: "no-store",
  });
  const body = await response.json().catch(() => null);

  if (!response.ok || !isAuthResponse(body)) {
    return NextResponse.json(body ?? { detail: response.statusText }, { status: response.status });
  }

  const nextResponse = NextResponse.json({ user: body.user }, { status: response.status });
  nextResponse.cookies.set(SESSION_COOKIE, body.token, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: 60 * 60 * 24 * 30,
  });
  return nextResponse;
}

function isAuthPayload(
  payload: unknown,
): payload is { workspace_id: string; password: string; display_name: string } {
  if (payload === null || typeof payload !== "object") {
    return false;
  }
  const candidate = payload as Record<string, unknown>;
  return (
    typeof candidate.workspace_id === "string" &&
    candidate.workspace_id.trim().length > 0 &&
    typeof candidate.display_name === "string" &&
    candidate.display_name.trim().length > 0 &&
    typeof candidate.password === "string" &&
    candidate.password.length >= 8
  );
}

function isAuthResponse(payload: unknown): payload is { token: string; user: unknown } {
  if (payload === null || typeof payload !== "object") {
    return false;
  }
  const candidate = payload as Record<string, unknown>;
  return typeof candidate.token === "string" && typeof candidate.user === "object";
}
