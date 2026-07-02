import {
  AlertTriangle,
  Clock3,
  ExternalLink,
  GitBranch,
  RadioTower,
  Terminal,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { RunActivity } from "@/components/run-activity";
import { AnswerCard } from "@/components/run-console/answer-card";
import { ClaimPill } from "@/components/run-console/claim-pill";
import { QuestionCard } from "@/components/run-console/question-card";
import { RunMeta } from "@/components/run-console/run-meta";
import { WaitingOutput } from "@/components/run-console/waiting-output";
import { formatSeconds } from "@/lib/metrics";
import { outputBlocksFromText } from "@/lib/run-output";
import type { DashboardRun } from "@/lib/types";

type CurrentRunConsoleProps = {
  run: DashboardRun | null;
  publicApiBaseUrl?: string;
  source: "api" | "demo";
  embedded?: boolean;
};

const activeStatuses: DashboardRun["status"][] = ["queued", "running"];

export function CurrentRunConsole({
  run,
  publicApiBaseUrl,
  source,
  embedded = false,
}: CurrentRunConsoleProps) {
  if (!run) {
    return (
      <section className="rounded-lg border border-border bg-card p-4">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Terminal className="h-4 w-4" aria-hidden="true" />
          Waiting for a run.
        </div>
      </section>
    );
  }

  const isActive = activeStatuses.includes(run.status);
  const hasPendingOutput = isActive && run.finalOutput === null && run.error === null;
  const output = run.finalOutput ?? run.error ?? "";
  const outputBlocks = hasPendingOutput ? [] : outputBlocksFromText(output);

  return (
    <section
      className={
        embedded
          ? "grid grid-rows-[auto_auto] rounded-lg border border-border bg-card"
          : "grid min-h-[620px] grid-rows-[auto_1fr] overflow-hidden rounded-lg border border-border bg-card"
      }
    >
      <header className="border-b border-border bg-muted/60 px-4 py-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="min-w-0 space-y-1">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant={statusVariant(run.status)}>{run.status}</Badge>
              <span className="font-mono text-xs text-muted-foreground">job {run.jobId.slice(0, 8)}</span>
              <span className="font-mono text-xs text-muted-foreground">{source}</span>
            </div>
            <h2 className="truncate font-mono text-sm font-semibold text-foreground">{run.repoName}</h2>
          </div>
          <div className="flex flex-wrap gap-2">
            {run.traceUrl ? (
              <Button variant="outline" asChild>
                <a href={run.traceUrl} target="_blank" rel="noreferrer">
                  <ExternalLink className="mr-2 h-4 w-4" aria-hidden="true" />
                  Trace
                </a>
              </Button>
            ) : null}
            {publicApiBaseUrl ? (
              <Button variant="outline" asChild>
                <a href={`${publicApiBaseUrl}/docs`} target="_blank" rel="noreferrer">
                  <ExternalLink className="mr-2 h-4 w-4" aria-hidden="true" />
                  API
                </a>
              </Button>
            ) : null}
          </div>
        </div>
        <div className="mt-3 grid gap-2 text-xs sm:grid-cols-2 xl:grid-cols-4">
          <RunMeta icon={<GitBranch className="h-3.5 w-3.5" />} label="agent" value={run.agentName} />
          <RunMeta icon={<RadioTower className="h-3.5 w-3.5" />} label="tool" value={run.toolName ?? "none"} />
          <RunMeta icon={<Terminal className="h-3.5 w-3.5" />} label="mcp" value={run.mcpServer ?? "none"} />
          <RunMeta icon={<Clock3 className="h-3.5 w-3.5" />} label="latency" value={formatSeconds(run.latency)} />
        </div>
        <div className="mt-3">
          <RunActivity status={run.status} startedAt={run.createdAt} />
        </div>
      </header>

      <div className={embedded ? "p-4" : "overflow-y-auto p-4"}>
        <div className="rounded-md border border-border bg-background/80">
          <div className="border-b border-border px-4 py-3 font-mono text-xs text-muted-foreground">
            <span className="text-primary">$</span> wayfinder explain --repo {run.repoUrl}
          </div>
          <div className="space-y-4 p-4">
            <QuestionCard query={run.query} />

            <div className="grid gap-2 sm:grid-cols-3">
              <ClaimPill label="verified" value={run.verifiedCount} tone="success" />
              <ClaimPill label="unverified" value={run.unverifiedCount} tone="warning" />
              <ClaimPill label="contradicted" value={run.contradictedCount} tone="danger" />
            </div>

            {run.claimProvenance.length > 0 ? (
              <div className="rounded-md border border-border bg-background/60 p-3">
                <div className="mb-2 font-mono text-xs uppercase tracking-wide text-muted-foreground">
                  Claim provenance
                </div>
                <ul className="space-y-1">
                  {run.claimProvenance.map((row) => (
                    <li key={row.agent} className="text-xs text-foreground/90">
                      <span className="font-medium text-primary">{row.agent}</span>
                      {" — "}
                      {row.verified} verified, {row.unverified} unverified,{" "}
                      {row.contradicted} contradicted
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            {hasPendingOutput ? <WaitingOutput /> : null}

            {outputBlocks.map((block, index) => (
              <AnswerCard key={`${block.label}-${index}`} block={block} />
            ))}

            {run.errors.length > 0 ? (
              <AnswerCard
                block={{
                  label: "errors",
                  title: "Runtime errors",
                  body: run.errors.map((error) => `${error.node}: ${error.message}`).join("\n"),
                  tone: "danger",
                  icon: AlertTriangle,
                }}
              />
            ) : null}
          </div>
        </div>
      </div>
    </section>
  );
}

function statusVariant(status: DashboardRun["status"]) {
  if (status === "completed") {
    return "success";
  }
  if (status === "failed") {
    return "danger";
  }
  return "warning";
}
