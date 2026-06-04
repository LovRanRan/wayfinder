"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

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
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const selectedJobId = searchParams.get("job");
  const [selectedRun, setSelectedRun] = useState<DashboardRun | null>(() =>
    runFromJobId(runs, selectedJobId) ?? runs[0] ?? null,
  );

  const selectRun = useCallback(
    (run: DashboardRun | null) => {
      setSelectedRun(run);
      const params = new URLSearchParams(searchParams.toString());
      if (run === null) {
        params.delete("job");
      } else {
        params.set("job", run.jobId);
      }
      const suffix = params.toString();
      router.replace(suffix ? `${pathname}?${suffix}` : pathname, { scroll: false });
    },
    [pathname, router, searchParams],
  );

  useEffect(() => {
    setSelectedRun((currentRun) => {
      const linkedRun = runFromJobId(runs, selectedJobId);
      if (linkedRun !== null) {
        return linkedRun;
      }

      if (currentRun === null) {
        return runs[0] ?? null;
      }

      return runs.find((run) => run.jobId === currentRun.jobId) ?? currentRun;
    });
  }, [runs, selectedJobId]);

  const visibleRuns = useMemo(() => {
    if (selectedRun === null) {
      return runs;
    }

    return [selectedRun, ...runs.filter((run) => run.jobId !== selectedRun.jobId)];
  }, [runs, selectedRun]);

  return (
    <section className="grid gap-4 xl:grid-cols-[minmax(360px,0.78fr)_minmax(0,1.22fr)]">
      <div className="grid gap-4 self-start">
        <RunLauncher initialRun={selectedRun} onRunChange={selectRun} />
        <RunStatusTable
          runs={visibleRuns.slice(0, 6)}
          source={source}
          compact
          onSelectRun={selectRun}
          selectedJobId={selectedRun?.jobId ?? null}
        />
      </div>
      <CurrentRunConsole run={selectedRun} publicApiBaseUrl={publicApiBaseUrl} source={source} />
    </section>
  );
}

function runFromJobId(runs: DashboardRun[], jobId: string | null): DashboardRun | null {
  if (jobId === null) {
    return null;
  }
  return runs.find((run) => run.jobId === jobId) ?? null;
}
