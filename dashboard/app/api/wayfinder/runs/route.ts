import { NextRequest } from "next/server";

import { proxyWayfinderJson } from "@/lib/wayfinder-proxy";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  const limit = request.nextUrl.searchParams.get("limit") ?? "10";
  return proxyWayfinderJson(`/runs?limit=${encodeURIComponent(limit)}`);
}
