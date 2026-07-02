import { redirect } from "next/navigation";

import { AppShell } from "@/components/app-shell";
import { WorkspaceSettingsPanel } from "@/components/workspace-settings";
import { getDashboardData } from "@/lib/api";

export default async function SettingsPage() {
  const { user, source, publicApiBaseUrl } = await getDashboardData();

  if (user === null) {
    redirect("/");
  }

  return (
    <AppShell active="settings" user={user} source={source} publicApiBaseUrl={publicApiBaseUrl}>
      <WorkspaceSettingsPanel />
    </AppShell>
  );
}
