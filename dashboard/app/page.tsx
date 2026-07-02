import { ExternalLink } from "lucide-react";

import { AgentWorkbench } from "@/components/agent-workbench";
import { AppShell } from "@/components/app-shell";
import { AuthPanel } from "@/components/auth-panel";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { getDashboardData } from "@/lib/api";

export default async function DashboardPage() {
  const { runs, threads, user, source, publicApiBaseUrl } = await getDashboardData();

  if (user === null) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-background px-4 py-8 text-foreground">
        <div className="grid w-full max-w-md gap-4">
          <header className="rounded-lg border border-border bg-card px-5 py-5 shadow-sm">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="success">Wayfinder</Badge>
              <Badge variant={source === "api" ? "warning" : "danger"}>
                {source === "api" ? "Login required" : "API unavailable"}
              </Badge>
            </div>
            <h1 className="mt-3 text-title font-semibold">
              Private codebase onboarding workspace
            </h1>
            <p className="mt-2 text-xs text-muted-foreground">api {publicApiBaseUrl}</p>
            <div className="mt-4">
              <Button variant="outline" asChild>
                <a href={`${publicApiBaseUrl}/docs`} target="_blank" rel="noreferrer">
                  <ExternalLink className="mr-2 h-4 w-4" aria-hidden="true" />
                  API docs
                </a>
              </Button>
            </div>
          </header>
          <AuthPanel />
        </div>
      </main>
    );
  }

  return (
    <AppShell
      active="threads"
      user={user}
      source={source}
      publicApiBaseUrl={publicApiBaseUrl}
      contentScroll={false}
    >
      <AgentWorkbench runs={runs} threads={threads} source={source} />
    </AppShell>
  );
}
