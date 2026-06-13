"use client";

import { useState } from "react";
import {
  BarChart3,
  GitBranch,
  MessageSquare,
  ShieldCheck,
  TriangleAlert,
  type LucideIcon,
} from "lucide-react";

import { formatPercent } from "@/lib/metrics";
import type { DashboardMetrics, DashboardThread } from "@/lib/types";

type DashboardStatsProps = {
  metrics: DashboardMetrics;
  threads: DashboardThread[];
  onOpenMetrics: () => void;
};

type MetricTabId = "threads" | "grounding" | "context" | "attention";

export function DashboardStats({ metrics, threads, onOpenMetrics }: DashboardStatsProps) {
  const [activeTab, setActiveTab] = useState<MetricTabId>("threads");
  // Top stats reflect active conversations only; archived threads are excluded.
  const visibleThreads = threads.filter((thread) => thread.status !== "archived");
  const activeThreads = visibleThreads.filter((thread) => thread.status === "running").length;
  const groundedAnswers = visibleThreads.reduce(
    (total, thread) =>
      total +
      thread.messages.filter(
        (message) =>
          message.role === "assistant" &&
          (message.verifiedCount + message.unverifiedCount + message.contradictedCount > 0 ||
            message.sourceRunId !== null),
      ).length,
    0,
  );
  const repoCount = new Set(visibleThreads.map((thread) => thread.repoUrl)).size;
  const attentionCount =
    activeThreads + metrics.failedRuns + (metrics.contradictedClaims > 0 ? 1 : 0);
  const tabs: MetricTab[] = [
    {
      id: "threads",
      icon: MessageSquare,
      label: "Threads",
      eyebrow: "Repo conversations",
      value: visibleThreads.length.toString(),
      detail: `${activeThreads} running · ${repoCount} repos`,
    },
    {
      id: "grounding",
      icon: ShieldCheck,
      label: "Grounding",
      eyebrow: "Evidence-backed answers",
      value: groundedAnswers.toString(),
      detail: `${metrics.verifiedClaims} verified · ${metrics.unverifiedClaims} unverified`,
    },
    {
      id: "context",
      icon: GitBranch,
      label: "Context",
      eyebrow: "Active repo scope",
      value: repoCount.toString(),
      detail: `${visibleThreads.length} threads · ${formatPercent(metrics.verificationRate)} verification rate`,
    },
    {
      id: "attention",
      icon: TriangleAlert,
      label: "Attention",
      eyebrow: "Items needing review",
      value: attentionCount.toString(),
      detail: `${metrics.failedRuns} failed runs · ${metrics.contradictedClaims} contradicted claims`,
    },
  ];
  const selected = tabs.find((tab) => tab.id === activeTab) ?? tabs[0];
  const SelectedIcon = selected.icon;

  return (
    <section className="rounded-lg border border-border bg-card/95 p-3 text-card-foreground">
      <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
        {tabs.map((tab) => (
          <MetricTabButton
            key={tab.id}
            icon={tab.icon}
            label={tab.label}
            isActive={tab.id === selected.id}
            onClick={() => setActiveTab(tab.id)}
          />
        ))}
      </div>
      <div className="mt-3 rounded-md border border-border bg-background/60 p-4">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <div className="flex items-center gap-2">
              <SelectedIcon className="h-4 w-4 text-primary" aria-hidden="true" />
              <span className="font-mono text-xs font-medium uppercase text-muted-foreground">
                {selected.eyebrow}
              </span>
            </div>
            <div className="mt-3 font-mono text-3xl font-semibold">{selected.value}</div>
            <p className="mt-1 font-mono text-xs text-muted-foreground">{selected.detail}</p>
          </div>
          <button
            type="button"
            className="inline-flex h-10 items-center justify-center gap-2 rounded-md border border-border px-3 font-mono text-xs font-semibold uppercase text-muted-foreground transition hover:border-primary/60 hover:text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            onClick={onOpenMetrics}
          >
            <BarChart3 className="h-4 w-4" aria-hidden="true" />
            Metrics
          </button>
        </div>
      </div>
    </section>
  );
}

type MetricTab = {
  id: MetricTabId;
  icon: LucideIcon;
  label: string;
  eyebrow: string;
  value: string;
  detail: string;
};

type MetricTabButtonProps = {
  icon: LucideIcon;
  label: string;
  isActive: boolean;
  onClick: () => void;
};

function MetricTabButton({ icon: Icon, label, isActive, onClick }: MetricTabButtonProps) {
  return (
    <button
      type="button"
      className={`inline-flex h-12 items-center justify-center gap-2 rounded-md border px-3 font-mono text-sm font-semibold transition focus:outline-none focus:ring-2 focus:ring-ring ${
        isActive
          ? "border-primary bg-primary text-primary-foreground"
          : "border-border bg-background/50 text-muted-foreground hover:border-primary/60 hover:text-foreground"
      }`}
      onClick={onClick}
      aria-pressed={isActive}
    >
      <Icon className="h-4 w-4" aria-hidden="true" />
      {label}
    </button>
  );
}
