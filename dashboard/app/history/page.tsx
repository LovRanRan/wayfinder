import { redirect } from "next/navigation";

import { AppShell } from "@/components/app-shell";
import { HistoryView } from "@/components/history-view";
import { getDashboardData } from "@/lib/api";

export default async function HistoryPage() {
  const { runs, threads, user, source, publicApiBaseUrl } = await getDashboardData();

  if (user === null) {
    redirect("/");
  }

  return (
    <AppShell active="history" user={user} source={source} publicApiBaseUrl={publicApiBaseUrl}>
      <HistoryView threads={threads} runs={runs} source={source} />
    </AppShell>
  );
}
