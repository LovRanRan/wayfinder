import { ExternalLink } from "lucide-react";

import { AgentWorkbench } from "@/components/agent-workbench";
import { AuthPanel } from "@/components/auth-panel";
import { WorkspaceAccount } from "@/components/workspace-account";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { getDashboardData } from "@/lib/api";

export default async function DashboardPage() {
  const { runs, user, source, publicApiBaseUrl } = await getDashboardData();
  const latest = runs[0];

  if (user === null) {
    return (
      <main className="min-h-screen bg-background px-4 py-4 text-foreground md:px-6">
        <div className="mx-auto grid max-w-[1180px] gap-4">
          <header className="flex flex-col gap-3 rounded-lg border border-border bg-card px-4 py-4 md:flex-row md:items-center md:justify-between">
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="success">Wayfinder</Badge>
                <Badge variant={source === "api" ? "warning" : "danger"}>
                  {source === "api" ? "Login required" : "API unavailable"}
                </Badge>
              </div>
              <h1 className="mt-3 font-mono text-xl font-semibold">private codebase onboarding workspace</h1>
              <p className="mt-2 font-mono text-xs text-muted-foreground">api {publicApiBaseUrl}</p>
            </div>
            <Button asChild>
              <a href={`${publicApiBaseUrl}/docs`} target="_blank" rel="noreferrer">
                <ExternalLink className="mr-2 h-4 w-4" aria-hidden="true" />
                API docs
              </a>
            </Button>
          </header>
          <AuthPanel />
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-background px-4 py-4 text-foreground md:px-6">
      <div className="mx-auto flex max-w-[1500px] flex-col gap-4">
        <header className="grid gap-4 rounded-lg border border-border bg-card px-4 py-4 xl:grid-cols-[1fr_360px]">
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <Badge variant="success">Wayfinder workspace</Badge>
              <Badge variant={source === "api" ? "success" : "warning"}>
                {source === "api" ? "Live API" : "Fallback sample"}
              </Badge>
            </div>
            <div>
              <h1 className="font-mono text-xl font-semibold tracking-normal">wayfinder</h1>
              <p className="mt-2 max-w-3xl font-mono text-xs leading-6 text-muted-foreground">
                private run history · repo evidence · verification labels · MCP traces
              </p>
              <p className="mt-1 font-mono text-[11px] text-muted-foreground">api {publicApiBaseUrl}</p>
            </div>
          </div>
          <div className="grid gap-3">
            <WorkspaceAccount user={user} />
            <div className="flex flex-wrap justify-end gap-2">
              {source === "api" && latest?.traceUrl ? (
                <Button variant="outline" asChild>
                  <a href={latest.traceUrl} target="_blank" rel="noreferrer">
                    <ExternalLink className="mr-2 h-4 w-4" aria-hidden="true" />
                    View traces
                  </a>
                </Button>
              ) : (
                <Button variant="outline" disabled>
                  <ExternalLink className="mr-2 h-4 w-4" aria-hidden="true" />
                  Trace pending
                </Button>
              )}
              <Button asChild>
                <a href={`${publicApiBaseUrl}/docs`} target="_blank" rel="noreferrer">
                  <ExternalLink className="mr-2 h-4 w-4" aria-hidden="true" />
                  API docs
                </a>
              </Button>
            </div>
          </div>
        </header>

        <AgentWorkbench
          runs={runs}
          source={source}
          publicApiBaseUrl={publicApiBaseUrl}
        />
      </div>
    </main>
  );
}
