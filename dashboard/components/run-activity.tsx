import { Bot, Database, GitBranch, ListChecks } from "lucide-react";

import type { RunStatus } from "@/lib/types";

type RunActivityProps = {
  status: RunStatus;
};

const activeStatuses: RunStatus[] = ["queued", "running"];

export function RunActivity({ status }: RunActivityProps) {
  if (!activeStatuses.includes(status)) {
    return null;
  }

  const steps = [
    { label: "route", icon: GitBranch },
    { label: "evidence", icon: Database },
    { label: "synthesis", icon: Bot },
    { label: "labels", icon: ListChecks },
  ];

  return (
    <div className="rounded-md border border-primary/30 bg-primary/10 p-3">
      <div className="flex items-center gap-2 font-mono text-xs text-primary">
        <span className="relative flex h-2.5 w-2.5">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary opacity-60" />
          <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-primary" />
        </span>
        Agent run in progress
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
              <span className="truncate font-mono text-[10px] uppercase text-muted-foreground">
                {step.label}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
