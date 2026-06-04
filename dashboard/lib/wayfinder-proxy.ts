import { NextResponse } from "next/server";

import { apiBaseUrlFromEnv } from "@/lib/api";
import { authorizationHeader, sessionTokenFromCookies } from "@/lib/session";

type JsonBody = Record<string, unknown> | unknown[];

export async function proxyWayfinderJson(
  path: string,
  init: {
    method?: "GET" | "POST";
    body?: JsonBody;
  } = {},
) {
  const method = init.method ?? "GET";
  const token = await sessionTokenFromCookies();
  const headers = {
    ...authorizationHeader(token),
    ...(init.body ? { "content-type": "application/json" } : {}),
  };

  try {
    const response = await fetch(`${apiBaseUrlFromEnv()}${path}`, {
      method,
      headers,
      body: init.body ? JSON.stringify(init.body) : undefined,
      cache: "no-store",
    });

    const payload = await responsePayload(response);
    return NextResponse.json(payload, { status: response.status });
  } catch {
    return NextResponse.json(
      { detail: "Wayfinder API is unavailable from the dashboard service." },
      { status: 502 },
    );
  }
}

async function responsePayload(response: Response): Promise<unknown> {
  const contentType = response.headers.get("content-type") ?? "";
  if (contentType.includes("application/json")) {
    return response.json();
  }

  const text = await response.text();
  return text.length > 0 ? { detail: text } : { detail: response.statusText };
}
