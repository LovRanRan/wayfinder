"use client";

import {
  Activity,
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

export function DashboardStats({ metrics, onOpenMetrics }: DashboardStatsProps) {
  const cards: StatButtonProps[] = [
    {
      icon: ShieldCheck,
      label: "Verification rate",
      value: formatPercent(metrics.verificationRate),
      detail: `${metrics.verifiedClaims} verified claims`,
      onClick: onOpenMetrics,
    },
    {
      icon: Activity,
      label: "Active runs",
      value: metrics.activeRuns.toString(),
      detail: `${metrics.totalRuns} recent runs tracked`,
      onClick: onOpenMetrics,
    },
    {
      icon: TimerReset,
      label: "P95 latency",
      value: formatSeconds(metrics.p95Latency),
      detail: `P50 ${formatSeconds(metrics.p50Latency)}`,
      onClick: onOpenMetrics,
    },
    {
      icon: CircleDollarSign,
      label: "Cost",
      value: formatCurrency(metrics.totalCostUsd),
      detail: `${metrics.totalTokens} tokens recorded`,
      onClick: onOpenMetrics,
    },
  ];

  return (
    <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
      {cards.map((card) => (
        <StatButton key={card.label} {...card} />
      ))}
    </section>
  );
}

type StatButtonProps = {
  icon: LucideIcon;
  label: string;
  value: string;
  detail: string;
  onClick: () => void;
};

function StatButton({ icon: Icon, label, value, detail, onClick }: StatButtonProps) {
  return (
    <button
      type="button"
      className="group rounded-lg border border-border bg-card/95 p-4 text-left text-card-foreground transition hover:border-primary/60 hover:bg-muted/50 focus:outline-none focus:ring-2 focus:ring-ring"
      onClick={onClick}
    >
      <div className="flex items-center justify-between gap-3">
        <span className="font-mono text-xs font-medium uppercase text-muted-foreground">{label}</span>
        <Icon className="h-4 w-4 text-primary transition group-hover:scale-105" aria-hidden="true" />
      </div>
      <div className="mt-3 font-mono text-2xl font-semibold">{value}</div>
      <p className="mt-1 font-mono text-[11px] text-muted-foreground">{detail}</p>
    </button>
  );
}
