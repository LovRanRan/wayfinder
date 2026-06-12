import { proxyWayfinderJson } from "@/lib/wayfinder-proxy";

export const dynamic = "force-dynamic";

export async function DELETE() {
  return proxyWayfinderJson("/workspace/context", {
    method: "DELETE",
  });
}
