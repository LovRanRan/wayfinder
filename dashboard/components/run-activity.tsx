"use client";

import { useEffect, useState } from "react";
import { Bot, Clock3, Database, GitBranch, ListChecks } from "lucide-react";

import type { RunStatus } from "@/lib/types";

type RunActivityProps = {
  status: RunStatus;
  startedAt?: string;
  label?: string;
};

const activeStatuses: RunStatus[] = ["queued", "running"];

export function RunActivity({ status, startedAt, label = "Agent run in progress" }: RunActivityProps) {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (!activeStatuses.includes(status)) {
      return;
    }

    setNow(Date.now());
    const timer = window.setInterval(() => {
      setNow(Date.now());
    }, 1000);

    return () => window.clearInterval(timer);
  }, [status]);

  if (!activeStatuses.includes(status)) {
    return null;
  }

  const elapsedSeconds = elapsedFrom(startedAt, now);

  const steps = [
    { label: "route", icon: GitBranch },
    { label: "evidence", icon: Database },
    { label: "synthesis", icon: Bot },
    { label: "labels", icon: ListChecks },
  ];

  return (
    <div className="rounded-md border border-primary/30 bg-primary/10 p-3" aria-live="polite">
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-primary">
        <div className="flex items-center gap-2">
          <span className="relative flex h-2.5 w-2.5">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary opacity-60" />
            <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-primary" />
          </span>
          {label}
        </div>
        <div className="flex items-center gap-1.5 rounded-sm border border-primary/30 bg-background/60 px-2 py-1 text-primary">
          <Clock3 className="h-3.5 w-3.5" aria-hidden="true" />
          <span>Elapsed {formatElapsed(elapsedSeconds)}</span>
        </div>
      </div>
      <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-background/80">
        <div className="h-full w-2/3 animate-pulse rounded-full bg-primary/80" />
      </div>
      <div className="mt-3 grid grid-cols-4 gap-2">
        {steps.map((step, index) => {
          const Icon = step.icon;
          return (
            <div
              key={step.label}
              className="flex min-w-0 items-center gap-1.5 rounded-md border border-border bg-background/70 px-2 py-1.5"
              style={{ animationDelay: `${index * 140}ms` }}
            >
              <Icon className="h-3.5 w-3.5 shrink-0 animate-pulse text-primary" aria-hidden="true" />
              <span className="truncate text-[10px] uppercase text-muted-foreground">
                {step.label}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function elapsedFrom(startedAt: string | undefined, now: number) {
  if (!startedAt) {
    return 0;
  }
  const started = Date.parse(startedAt);
  if (Number.isNaN(started)) {
    return 0;
  }
  return Math.max(0, Math.floor((now - started) / 1000));
}

function formatElapsed(seconds: number) {
  const minutes = Math.floor(seconds / 60);
  const remaining = seconds % 60;
  return `${minutes}:${remaining.toString().padStart(2, "0")}`;
}
