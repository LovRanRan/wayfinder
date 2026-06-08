"use client";

import { useState } from "react";
import {
  BarChart3,
  CheckCircle2,
  CircleDollarSign,
  ShieldCheck,
  TimerReset,
  type LucideIcon,
} from "lucide-react";

import { formatCurrency, formatPercent, formatSeconds } from "@/lib/metrics";
import type { DashboardMetrics } from "@/lib/types";

type DashboardStatsProps = {
  metrics: DashboardMetrics;
  onOpenMetrics: () => void;
};

type MetricTabId = "success" | "runs" | "latency" | "cost";

export function DashboardStats({ metrics, onOpenMetrics }: DashboardStatsProps) {
  const [activeTab, setActiveTab] = useState<MetricTabId>("success");
  const tabs: MetricTab[] = [
    {
      id: "success",
      icon: ShieldCheck,
      label: "Success",
      eyebrow: "Run success rate",
      value: formatPercent(metrics.successRate),
      detail: `${metrics.completedRuns} completed / ${metrics.failedRuns} failed`,
    },
    {
      id: "runs",
      icon: CheckCircle2,
      label: "Runs",
      eyebrow: "Completed runs",
      value: metrics.completedRuns.toString(),
      detail: `${metrics.totalRuns} recent runs tracked`,
    },
    {
      id: "latency",
      icon: TimerReset,
      label: "Latency",
      eyebrow: "Latest completed latency",
      value: formatSeconds(metrics.latestCompletedLatency),
      detail: `${metrics.completedLatencySamples} completed samples · P95 ${formatSeconds(metrics.p95Latency)}`,
    },
    {
      id: "cost",
      icon: CircleDollarSign,
      label: "Cost",
      eyebrow: "App-tracked cost",
      value: formatCurrency(metrics.totalCostUsd),
      detail: `${metrics.totalTokens} tokens recorded`,
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
