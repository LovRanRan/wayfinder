import {
  AlertTriangle,
  CheckCircle2,
  Clock3,
  ExternalLink,
  GitBranch,
  RadioTower,
  Terminal,
} from "lucide-react";
import type { ReactNode } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { formatSeconds } from "@/lib/metrics";
import type { DashboardRun } from "@/lib/types";

type CurrentRunConsoleProps = {
  run: DashboardRun | null;
  publicApiBaseUrl: string;
  source: "api" | "demo";
};

export function CurrentRunConsole({ run, publicApiBaseUrl, source }: CurrentRunConsoleProps) {
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

  const output = run.finalOutput ?? run.error ?? "Run is still producing output.";
  const outputBlocks = outputBlocksFromText(output);

  return (
    <section className="grid min-h-[620px] grid-rows-[auto_1fr] overflow-hidden rounded-lg border border-border bg-card">
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
            <Button variant="outline" asChild>
              <a href={`${publicApiBaseUrl}/docs`} target="_blank" rel="noreferrer">
                <ExternalLink className="mr-2 h-4 w-4" aria-hidden="true" />
                API
              </a>
            </Button>
          </div>
        </div>
        <div className="mt-3 grid gap-2 text-xs sm:grid-cols-2 xl:grid-cols-4">
          <RunMeta icon={<GitBranch className="h-3.5 w-3.5" />} label="agent" value={run.agentName} />
          <RunMeta icon={<RadioTower className="h-3.5 w-3.5" />} label="tool" value={run.toolName ?? "none"} />
          <RunMeta icon={<Terminal className="h-3.5 w-3.5" />} label="mcp" value={run.mcpServer ?? "none"} />
          <RunMeta icon={<Clock3 className="h-3.5 w-3.5" />} label="latency" value={formatSeconds(run.latency)} />
        </div>
      </header>

      <div className="overflow-y-auto p-4">
        <div className="rounded-md border border-border bg-background/80">
          <div className="border-b border-border px-4 py-3 font-mono text-xs text-muted-foreground">
            <span className="text-primary">$</span> wayfinder explain --repo {run.repoUrl}
          </div>
          <div className="space-y-4 p-4">
            <TranscriptBlock label="question" tone="muted">
              {run.query}
            </TranscriptBlock>

            <div className="grid grid-cols-3 gap-2">
              <ClaimPill label="verified" value={run.verifiedCount} tone="success" />
              <ClaimPill label="unverified" value={run.unverifiedCount} tone="warning" />
              <ClaimPill label="contradicted" value={run.contradictedCount} tone="danger" />
            </div>

            {outputBlocks.map((block, index) => (
              <TranscriptBlock key={`${block.label}-${index}`} label={block.label} tone={block.tone}>
                {block.body}
              </TranscriptBlock>
            ))}

            {run.errors.length > 0 ? (
              <TranscriptBlock label="errors" tone="danger">
                {run.errors.map((error) => `${error.node}: ${error.message}`).join("\n")}
              </TranscriptBlock>
            ) : null}
          </div>
        </div>
      </div>
    </section>
  );
}

type OutputBlock = {
  label: string;
  body: string;
  tone: "muted" | "success" | "warning" | "danger";
};

function outputBlocksFromText(output: string): OutputBlock[] {
  const paragraphs = output
    .split(/\n{2,}/)
    .map((paragraph) => paragraph.trim())
    .filter(Boolean);

  if (paragraphs.length === 0) {
    return [{ label: "output", body: output, tone: "muted" }];
  }

  return paragraphs.map((paragraph) => {
    const lowered = paragraph.toLowerCase();
    if (lowered.startsWith("verification summary")) {
      return { label: "verification", body: paragraph, tone: "warning" };
    }
    if (lowered.startsWith("unverified claims")) {
      return { label: "unverified", body: paragraph, tone: "warning" };
    }
    if (lowered.startsWith("contradicted")) {
      return { label: "contradiction", body: paragraph, tone: "danger" };
    }
    if (lowered.includes("definition:") || lowered.includes("source citations:")) {
      return { label: "evidence", body: paragraph, tone: "success" };
    }

    return { label: "answer", body: paragraph, tone: "muted" };
  });
}

function TranscriptBlock({
  label,
  tone,
  children,
}: {
  label: string;
  tone: "muted" | "success" | "warning" | "danger";
  children: string;
}) {
  return (
    <div className="grid gap-2 border-l pl-3" data-tone={tone}>
      <div className={labelClass(tone)}>{label}</div>
      <pre className="whitespace-pre-wrap break-words font-mono text-sm leading-6 text-foreground">{children}</pre>
    </div>
  );
}

function RunMeta({ icon, label, value }: { icon: ReactNode; label: string; value: string }) {
  return (
    <div className="flex min-w-0 items-center gap-2 rounded-md border border-border bg-background/70 px-2.5 py-2">
      <span className="text-muted-foreground">{icon}</span>
      <span className="shrink-0 font-mono text-[10px] uppercase text-muted-foreground">{label}</span>
      <span className="truncate font-mono text-xs text-foreground">{value}</span>
    </div>
  );
}

function ClaimPill({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: "success" | "warning" | "danger";
}) {
  const Icon = tone === "success" ? CheckCircle2 : AlertTriangle;
  return (
    <div className="rounded-md border border-border bg-muted/60 px-3 py-2">
      <div className="flex items-center gap-2">
        <Icon className={iconClass(tone)} aria-hidden="true" />
        <span className="font-mono text-lg font-semibold">{value}</span>
      </div>
      <div className="mt-1 font-mono text-[10px] uppercase text-muted-foreground">{label}</div>
    </div>
  );
}

function labelClass(tone: "muted" | "success" | "warning" | "danger") {
  const base = "font-mono text-[11px] uppercase";
  if (tone === "success") {
    return `${base} text-success`;
  }
  if (tone === "warning") {
    return `${base} text-warning`;
  }
  if (tone === "danger") {
    return `${base} text-danger`;
  }
  return `${base} text-muted-foreground`;
}

function iconClass(tone: "success" | "warning" | "danger") {
  const base = "h-4 w-4";
  if (tone === "success") {
    return `${base} text-success`;
  }
  if (tone === "warning") {
    return `${base} text-warning`;
  }
  return `${base} text-danger`;
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
