"use client";

import { useEffect, useMemo, useState } from "react";

import { CurrentRunConsole } from "@/components/current-run-console";
import { RunLauncher } from "@/components/run-launcher";
import { RunStatusTable } from "@/components/run-status-table";
import type { DashboardRun } from "@/lib/types";

type AgentWorkbenchProps = {
  runs: DashboardRun[];
  source: "api" | "demo";
  publicApiBaseUrl: string;
};

export function AgentWorkbench({ runs, source, publicApiBaseUrl }: AgentWorkbenchProps) {
  const [selectedRun, setSelectedRun] = useState<DashboardRun | null>(() => runs[0] ?? null);

  useEffect(() => {
    setSelectedRun((currentRun) => {
      if (currentRun === null) {
        return runs[0] ?? null;
      }

      return runs.find((run) => run.jobId === currentRun.jobId) ?? currentRun;
    });
  }, [runs]);

  const visibleRuns = useMemo(() => {
    if (selectedRun === null) {
      return runs;
    }

    return [selectedRun, ...runs.filter((run) => run.jobId !== selectedRun.jobId)];
  }, [runs, selectedRun]);

  return (
    <section className="grid gap-4 xl:grid-cols-[minmax(360px,0.78fr)_minmax(0,1.22fr)]">
      <div className="grid gap-4 self-start">
        <RunLauncher initialRun={selectedRun} onRunChange={setSelectedRun} />
        <RunStatusTable
          runs={visibleRuns.slice(0, 6)}
          source={source}
          compact
          onSelectRun={setSelectedRun}
          selectedJobId={selectedRun?.jobId ?? null}
        />
      </div>
      <CurrentRunConsole run={selectedRun} publicApiBaseUrl={publicApiBaseUrl} source={source} />
    </section>
  );
}
