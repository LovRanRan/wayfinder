import { proxyWayfinderJson } from "@/lib/wayfinder-proxy";

export const dynamic = "force-dynamic";

export async function GET() {
  return proxyWayfinderJson("/auth/me");
}
