import {
  AlertTriangle,
  BookOpenText,
  CheckCircle2,
  Clock3,
  Code2,
  ExternalLink,
  FileText,
  GitBranch,
  ListChecks,
  Network,
  RadioTower,
  ShieldCheck,
  Terminal,
} from "lucide-react";
import type { ReactNode } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { RunActivity } from "@/components/run-activity";
import { formatSeconds } from "@/lib/metrics";
import type { DashboardRun } from "@/lib/types";

type CurrentRunConsoleProps = {
  run: DashboardRun | null;
  publicApiBaseUrl: string;
  source: "api" | "demo";
};

const activeStatuses: DashboardRun["status"][] = ["queued", "running"];

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

  const isActive = activeStatuses.includes(run.status);
  const hasPendingOutput = isActive && run.finalOutput === null && run.error === null;
  const output = run.finalOutput ?? run.error ?? "";
  const outputBlocks = hasPendingOutput ? [] : outputBlocksFromText(output);

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
        <div className="mt-3">
          <RunActivity status={run.status} startedAt={run.createdAt} />
        </div>
      </header>

      <div className="overflow-y-auto p-4">
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

type OutputTone = "muted" | "success" | "warning" | "danger" | "info";

type OutputBlock = {
  label: string;
  title: string;
  body: string;
  tone: OutputTone;
  icon: typeof Terminal;
};

function outputBlocksFromText(output: string): OutputBlock[] {
  const paragraphs = mergeHeadingParagraphs(
    output
      .split(/\n{2,}/)
      .map((paragraph) => paragraph.trim())
      .filter(Boolean),
  );

  if (paragraphs.length === 0) {
    return [
      {
        label: "output",
        title: "Output",
        body: "No answer content was returned.",
        tone: "muted",
        icon: FileText,
      },
    ];
  }

  return paragraphs.map(outputBlockFromParagraph);
}

function mergeHeadingParagraphs(paragraphs: string[]) {
  const merged: string[] = [];
  for (let index = 0; index < paragraphs.length; index += 1) {
    const paragraph = paragraphs[index];
    const next = paragraphs[index + 1];
    if (next && isStandaloneHeading(paragraph)) {
      merged.push(`${paragraph}\n${next}`);
      index += 1;
    } else {
      merged.push(paragraph);
    }
  }
  return merged;
}

function isStandaloneHeading(paragraph: string) {
  const lines = paragraph.split("\n");
  return lines.length === 1 && paragraph.length <= 90 && /:\s*$/.test(paragraph);
}

function outputBlockFromParagraph(paragraph: string): OutputBlock {
  const lines = paragraph.split("\n");
  const firstLine = lines[0]?.trim() ?? "";
  const hasHeading = isStandaloneHeading(firstLine) && lines.length > 1;
  const explicitTitle = hasHeading ? titleFromHeading(firstLine) : null;
  const body = hasHeading ? lines.slice(1).join("\n").trim() : paragraph;
  const searchable = `${explicitTitle ?? ""}\n${body}`.toLowerCase();

  if (searchable.includes("verification summary")) {
    return block("verification", explicitTitle ?? "Verification summary", body, "warning", ListChecks);
  }

  if (
    searchable.includes("error") ||
    searchable.includes("contradicted") ||
    searchable.includes("contradiction")
  ) {
    return block("contradiction", explicitTitle ?? "Contradiction or error", body, "danger", AlertTriangle);
  }

  if (
    searchable.includes("unverified") ||
    searchable.includes("limitation") ||
    searchable.includes("uncertainty") ||
    searchable.includes("cannot") ||
    searchable.includes("no test") ||
    searchable.includes("scan failed")
  ) {
    return block("limitation", explicitTitle ?? "Limitations and uncertainty", body, "warning", AlertTriangle);
  }

  if (
    searchable.includes("verified from ast") ||
    searchable.includes("source citations") ||
    searchable.includes("signature") ||
    searchable.includes("defined in")
  ) {
    return block("evidence", explicitTitle ?? "Verified evidence", body, "success", ShieldCheck);
  }

  if (
    searchable.includes("control-flow") ||
    searchable.includes("data flow") ||
    searchable.includes("architecture path") ||
    searchable.includes("entry explanation path") ||
    searchable.includes("verifier path")
  ) {
    return block("flow", explicitTitle ?? "Observed flow", body, "info", Network);
  }

  if (searchable.includes("behavior") || searchable.includes("function body")) {
    return block("behavior", explicitTitle ?? "Behavior", body, "muted", Code2);
  }

  if (searchable.includes("recommended") || searchable.includes("suggested")) {
    return block("next step", explicitTitle ?? "Recommended next step", body, "info", ListChecks);
  }

  return block("answer", explicitTitle ?? "Answer", body, "muted", FileText);
}

function block(
  label: string,
  title: string,
  body: string,
  tone: OutputTone,
  icon: typeof Terminal,
): OutputBlock {
  return {
    label,
    title,
    body: body.trim() || title,
    tone,
    icon,
  };
}

function titleFromHeading(heading: string) {
  return heading.replace(/:\s*$/, "").trim();
}

function QuestionCard({ query }: { query: string }) {
  return (
    <div className="rounded-md border border-border bg-muted/40 p-4">
      <div className="flex items-center gap-2 font-mono text-[11px] uppercase text-muted-foreground">
        <BookOpenText className="h-4 w-4 text-primary" aria-hidden="true" />
        Question
      </div>
      <p className="mt-3 text-sm font-medium leading-6 text-foreground">{query}</p>
    </div>
  );
}

function WaitingOutput() {
  const rows = ["routing intent", "collecting evidence", "synthesizing answer", "checking labels"];

  return (
    <div className="rounded-md border border-primary/30 bg-primary/5 p-4">
      <div className="flex items-center gap-2 font-mono text-[11px] uppercase text-primary">
        <Terminal className="h-4 w-4" aria-hidden="true" />
        Waiting for answer
      </div>
      <div className="mt-4 grid gap-2 md:grid-cols-2">
        {rows.map((row, index) => (
          <div key={row} className="rounded-md border border-border bg-background/70 p-3">
            <div className="flex items-center justify-between gap-3">
              <span className="font-mono text-xs text-muted-foreground">{row}</span>
              <span className="h-2 w-2 animate-pulse rounded-full bg-primary" style={{ animationDelay: `${index * 120}ms` }} />
            </div>
            <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-muted">
              <div className="h-full w-1/2 animate-pulse rounded-full bg-primary/80" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function AnswerCard({ block }: { block: OutputBlock }) {
  const Icon = block.icon;

  return (
    <article className={answerCardClass(block.tone)}>
      <div className="flex gap-3">
        <div className={answerIconClass(block.tone)}>
          <Icon className="h-4 w-4" aria-hidden="true" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className={answerLabelClass(block.tone)}>{block.label}</span>
            <h3 className="font-mono text-sm font-semibold text-foreground">{block.title}</h3>
          </div>
          <StructuredText text={block.body} />
        </div>
      </div>
    </article>
  );
}

function StructuredText({ text }: { text: string }) {
  const lines = text.split("\n");

  return (
    <div className="mt-3 space-y-1.5">
      {lines.map((line, index) => (
        <StructuredLine key={`${line}-${index}`} line={line} />
      ))}
    </div>
  );
}

function StructuredLine({ line }: { line: string }) {
  const indent = Math.min(3, Math.floor((line.match(/^\s*/)?.[0].length ?? 0) / 2));
  const trimmed = line.trim();

  if (!trimmed) {
    return <div className="h-1" />;
  }

  const bullet = trimmed.match(/^[-*]\s+(.*)$/);
  if (bullet) {
    return (
      <div className="flex gap-2 text-sm leading-6 text-foreground" style={{ paddingLeft: `${indent * 14}px` }}>
        <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-primary/80" />
        <span className="min-w-0 break-words">
          <InlineCodeText text={bullet[1]} />
        </span>
      </div>
    );
  }

  const numbered = trimmed.match(/^(\d+)\.\s+(.*)$/);
  if (numbered) {
    return (
      <div className="flex gap-2 text-sm leading-6 text-foreground" style={{ paddingLeft: `${indent * 14}px` }}>
        <span className="mt-0.5 flex h-5 min-w-5 shrink-0 items-center justify-center rounded-sm border border-border bg-muted px-1 font-mono text-[10px] text-muted-foreground">
          {numbered[1]}
        </span>
        <span className="min-w-0 break-words">
          <InlineCodeText text={numbered[2]} />
        </span>
      </div>
    );
  }

  return (
    <p className="break-words text-sm leading-6 text-foreground" style={{ paddingLeft: `${indent * 14}px` }}>
      <InlineCodeText text={trimmed} />
    </p>
  );
}

function InlineCodeText({ text }: { text: string }) {
  return text.split(/(`[^`]+`)/g).map((part, index) => {
    if (part.startsWith("`") && part.endsWith("`")) {
      return (
        <code
          key={`${part}-${index}`}
          className="rounded-sm border border-border bg-background px-1.5 py-0.5 font-mono text-[0.92em] text-primary"
        >
          {part.slice(1, -1)}
        </code>
      );
    }
    return <span key={`${part}-${index}`}>{part}</span>;
  });
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
        <Icon className={claimIconClass(tone)} aria-hidden="true" />
        <span className="font-mono text-lg font-semibold">{value}</span>
      </div>
      <div className="mt-1 font-mono text-[10px] uppercase text-muted-foreground">{label}</div>
    </div>
  );
}

function answerCardClass(tone: OutputTone) {
  const base = "rounded-md border p-4";
  if (tone === "success") {
    return `${base} border-success/30 bg-success/5`;
  }
  if (tone === "warning") {
    return `${base} border-warning/30 bg-warning/5`;
  }
  if (tone === "danger") {
    return `${base} border-danger/30 bg-danger/5`;
  }
  if (tone === "info") {
    return `${base} border-primary/30 bg-primary/5`;
  }
  return `${base} border-border bg-muted/30`;
}

function answerIconClass(tone: OutputTone) {
  const base = "mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-md border";
  if (tone === "success") {
    return `${base} border-success/30 bg-success/10 text-success`;
  }
  if (tone === "warning") {
    return `${base} border-warning/30 bg-warning/10 text-warning`;
  }
  if (tone === "danger") {
    return `${base} border-danger/30 bg-danger/10 text-danger`;
  }
  if (tone === "info") {
    return `${base} border-primary/30 bg-primary/10 text-primary`;
  }
  return `${base} border-border bg-background text-muted-foreground`;
}

function answerLabelClass(tone: OutputTone) {
  const base = "rounded-sm border px-1.5 py-0.5 font-mono text-[10px] uppercase";
  if (tone === "success") {
    return `${base} border-success/30 bg-success/10 text-success`;
  }
  if (tone === "warning") {
    return `${base} border-warning/30 bg-warning/10 text-warning`;
  }
  if (tone === "danger") {
    return `${base} border-danger/30 bg-danger/10 text-danger`;
  }
  if (tone === "info") {
    return `${base} border-primary/30 bg-primary/10 text-primary`;
  }
  return `${base} border-border bg-background text-muted-foreground`;
}

function claimIconClass(tone: "success" | "warning" | "danger") {
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
