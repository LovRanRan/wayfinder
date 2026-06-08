import { proxyWayfinderJson } from "@/lib/wayfinder-proxy";

export const dynamic = "force-dynamic";

type RouteParams = {
  params: Promise<{ threadId: string }>;
};

export async function GET(_request: Request, { params }: RouteParams) {
  const { threadId } = await params;
  return proxyWayfinderJson(`/threads/${encodeURIComponent(threadId)}`);
}
