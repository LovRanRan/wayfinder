import { redirect } from "next/navigation";

import { AppShell } from "@/components/app-shell";
import { WorkspaceMetrics } from "@/components/workspace-metrics";
import { getDashboardData } from "@/lib/api";

export default async function MetricsPage() {
  const { runs, user, source, publicApiBaseUrl } = await getDashboardData();

  if (user === null) {
    redirect("/");
  }

  return (
    <AppShell active="metrics" user={user} source={source} publicApiBaseUrl={publicApiBaseUrl}>
      <WorkspaceMetrics runs={runs} />
    </AppShell>
  );
}
