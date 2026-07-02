"use client";

import { BrainCircuit, PanelRight } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { runStatusVariant } from "@/lib/workspace-format";
import type { ActiveRepoContext, AgentTraceAttachment, DashboardRun } from "@/lib/types";

type ContextRailProps = {
  context: ActiveRepoContext | null;
  trace: AgentTraceAttachment | null;
  selectedRun: DashboardRun | null;
};

export function ContextRail({ context, trace, selectedRun }: ContextRailProps) {
  return (
    <aside className="grid min-h-0 grid-rows-[auto_1fr] gap-4">
      <ContextPanel context={context} selectedRun={selectedRun} />
      <AgentTracePanel trace={trace} selectedRun={selectedRun} />
    </aside>
  );
}

function ContextPanel({
  context,
  selectedRun,
}: {
  context: ActiveRepoContext | null;
  selectedRun: DashboardRun | null;
}) {
  return (
    <section className="rounded-lg border border-border bg-card p-4">
      <div className="flex items-center gap-2 text-sm font-semibold">
        <PanelRight className="h-4 w-4 text-primary" aria-hidden="true" />
        Context
      </div>
      <div className="mt-3 grid gap-3 text-xs">
        <ContextRow label="repo" value={context?.repoName ?? "none"} />
        <ContextRow label="focus" value={context?.activeFocus ?? "none"} />
        <ContextRow label="thread" value={context?.defaultThreadId ?? "none"} />
        <ContextRow label="run" value={selectedRun?.jobId ?? context?.lastRunId ?? "none"} />
      </div>
      {context?.summaryMemory ? (
        <p className="mt-3 line-clamp-5 rounded-md border border-border bg-background p-3 font-mono text-[11px] leading-5 text-muted-foreground">
          {context.summaryMemory}
        </p>
      ) : null}
    </section>
  );
}

function AgentTracePanel({
  trace,
  selectedRun,
}: {
  trace: AgentTraceAttachment | null;
  selectedRun: DashboardRun | null;
}) {
  return (
    <section className="min-h-0 overflow-hidden rounded-lg border border-border bg-card">
      <header className="border-b border-border bg-muted/60 px-4 py-3">
        <div className="flex items-center gap-2 text-sm font-semibold">
          <BrainCircuit className="h-4 w-4 text-primary" aria-hidden="true" />
          Agent trace
        </div>
      </header>
      <div className="max-h-full overflow-y-auto p-4">
        {trace === null ? (
          <p className="text-xs leading-5 text-muted-foreground">
            Grounded chat responses will attach route, agents, tools, verifier status, and run evidence here.
          </p>
        ) : (
          <div className="grid gap-3">
            <div className="rounded-md border border-border bg-background p-3">
              <div className="flex flex-wrap gap-2">
                <Badge variant="outline">{trace.route.intent}</Badge>
                <Badge variant="outline">{trace.route.answerMode}</Badge>
                {trace.route.requiresGroundedRun ? <Badge variant="warning">grounded</Badge> : null}
              </div>
              <p className="mt-2 font-mono text-[11px] leading-5 text-muted-foreground">
                {trace.route.reason}
              </p>
            </div>
            {trace.steps.map((step) => (
              <div key={`${step.agentName}-${step.task}`} className="rounded-md border border-border p-3">
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate font-mono text-xs font-semibold">{step.agentName}</span>
                  <Badge variant={step.status === "completed" ? "success" : "outline"}>
                    {step.status}
                  </Badge>
                </div>
                <p className="mt-2 font-mono text-[11px] leading-5 text-muted-foreground">
                  {step.task}
                </p>
              </div>
            ))}
            {trace.toolRefs.length > 0 ? (
              <div className="flex flex-wrap gap-2">
                {trace.toolRefs.map((tool) => (
                  <Badge key={tool} variant="outline">
                    {tool}
                  </Badge>
                ))}
              </div>
            ) : null}
          </div>
        )}
        {selectedRun !== null ? (
          <div className="mt-4 rounded-md border border-border bg-background p-3">
            <div className="text-xs font-semibold">Selected run</div>
            <div className="mt-2 flex flex-wrap gap-2">
              <Badge variant={runStatusVariant(selectedRun.status)}>{selectedRun.status}</Badge>
              <Badge variant="success">verified {selectedRun.verifiedCount}</Badge>
              <Badge variant="warning">unverified {selectedRun.unverifiedCount}</Badge>
            </div>
          </div>
        ) : null}
      </div>
    </section>
  );
}

function ContextRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-3 rounded-md border border-border bg-background p-2">
      <span className="shrink-0 uppercase text-muted-foreground">{label}</span>
      <span className="min-w-0 break-all text-right font-mono text-foreground">{value}</span>
    </div>
  );
}
