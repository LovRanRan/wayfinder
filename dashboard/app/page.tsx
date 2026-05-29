import { Activity, GitBranch, ShieldCheck, TimerReset } from "lucide-react";

import { RunStatusTable } from "@/components/run-status-table";
import { StatCard } from "@/components/stat-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { mockRuns } from "@/lib/mock-data";

export default function DashboardPage() {
  const latest = mockRuns[0];

  return (
    <main className="min-h-screen bg-muted px-6 py-6">
      <div className="mx-auto flex max-w-7xl flex-col gap-6">
        <header className="flex flex-col gap-4 border-b border-border pb-5 md:flex-row md:items-end md:justify-between">
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <Badge variant="outline">Commit 0 scaffold</Badge>
              <Badge variant="success">API shell ready</Badge>
            </div>
            <div>
              <h1 className="text-3xl font-semibold tracking-normal">wayfinder runs</h1>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
                Monitor codebase onboarding runs, verification status, traces, latency, and failure
                modes from one operational dashboard.
              </p>
            </div>
          </div>
          <div className="flex gap-2">
            <Button variant="outline">View traces</Button>
            <Button>Start run</Button>
          </div>
        </header>

        <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <StatCard
            icon={ShieldCheck}
            label="Verified claims"
            value={latest.verifiedCount.toString()}
            detail="Current run"
          />
          <StatCard
            icon={Activity}
            label="Contradicted"
            value={latest.contradictedCount.toString()}
            detail="Needs rewrite"
          />
          <StatCard
            icon={TimerReset}
            label="P95 latency"
            value="4.2s"
            detail="Agent node placeholder"
          />
          <StatCard
            icon={GitBranch}
            label="Route"
            value={latest.intent}
            detail="Supervisor decision"
          />
        </section>

        <RunStatusTable runs={mockRuns} />
      </div>
    </main>
  );
}
