"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Loader2,
  Play,
  RefreshCw,
  RotateCcw,
  Send,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { formatSeconds, toDashboardRun } from "@/lib/metrics";
import type { ApiRunSummary, DashboardRun, RunStatus } from "@/lib/types";

const SAMPLE_REPO = "https://github.com/LovRanRan/wayfinder";
const SAMPLE_QUERY = "Explain the behavior and data flow through wayfinder.graph.app.build_graph";
const terminalStatuses: RunStatus[] = ["completed", "failed"];

type RunLauncherProps = {
  initialRun?: DashboardRun | null;
  onRunChange?: (run: DashboardRun | null) => void;
};

export function RunLauncher({ initialRun = null, onRunChange }: RunLauncherProps) {
  const [repoUrl, setRepoUrl] = useState(SAMPLE_REPO);
  const [query, setQuery] = useState(SAMPLE_QUERY);
  const [correction, setCorrection] = useState("");
  const [run, setRun] = useState<DashboardRun | null>(initialRun);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isRefining, setIsRefining] = useState(false);

  useEffect(() => {
    setRun(initialRun);
  }, [initialRun]);

  const updateRun = useCallback(
    (nextRun: DashboardRun) => {
      setRun(nextRun);
      onRunChange?.(nextRun);
    },
    [onRunChange],
  );

  const refreshRun = useCallback(
    async (silent = false) => {
      if (!run) {
        return;
      }

      if (!silent) {
        setIsRefreshing(true);
      }
      setError(null);

      try {
        const payload = await fetchRun(`/api/wayfinder/status/${encodeURIComponent(run.jobId)}`);
        updateRun(toDashboardRun(payload));
      } catch (refreshError) {
        setError(errorMessage(refreshError));
      } finally {
        if (!silent) {
          setIsRefreshing(false);
        }
      }
    },
    [run, updateRun],
  );

  useEffect(() => {
    if (!run || terminalStatuses.includes(run.status)) {
      return;
    }

    const timer = window.setTimeout(() => {
      void refreshRun(true);
    }, 1400);

    return () => window.clearTimeout(timer);
  }, [refreshRun, run]);

  async function submitRun(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    setError(null);
    setRun(null);

    try {
      const payload = await fetchRun("/api/wayfinder/explain", {
        method: "POST",
        body: JSON.stringify({
          repo_url: repoUrl.trim(),
          query: query.trim(),
        }),
      });
      updateRun(toDashboardRun(payload));
    } catch (submitError) {
      setError(errorMessage(submitError));
    } finally {
      setIsSubmitting(false);
    }
  }

  async function submitRefine(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!run) {
      return;
    }

    setIsRefining(true);
    setError(null);

    try {
      const payload = await fetchRun(`/api/wayfinder/refine/${encodeURIComponent(run.jobId)}`, {
        method: "POST",
        body: JSON.stringify({ correction: correction.trim() }),
      });
      updateRun(toDashboardRun(payload));
      setCorrection("");
    } catch (refineError) {
      setError(errorMessage(refineError));
    } finally {
      setIsRefining(false);
    }
  }

  const canSubmit = repoUrl.trim().length > 0 && query.trim().length > 0 && !isSubmitting;
  const canRefine = run !== null && correction.trim().length > 0 && !isRefining;

  return (
    <section className="overflow-hidden rounded-lg border border-border bg-card">
      <header className="flex items-start justify-between gap-3 border-b border-border bg-muted/60 px-4 py-3">
        <div>
          <div className="flex items-center gap-2 font-mono text-sm font-semibold">
            <Play className="h-4 w-4 text-primary" aria-hidden="true" />
            Run composer
          </div>
          <p className="mt-1 font-mono text-xs text-muted-foreground">repo + question to agent trace</p>
        </div>
        {run ? <Badge variant={statusVariant(run.status)}>{run.status}</Badge> : null}
      </header>
      <div className="space-y-4 p-4">
        <form className="grid gap-3" onSubmit={submitRun}>
          <label className="grid gap-1.5 font-mono text-xs uppercase text-muted-foreground">
            repo
            <input
              className="h-10 rounded-md border border-border bg-background px-3 font-mono text-sm normal-case text-foreground outline-none transition placeholder:text-muted-foreground focus:border-primary"
              value={repoUrl}
              onChange={(event) => setRepoUrl(event.target.value)}
              placeholder="https://github.com/owner/repo"
            />
          </label>
          <label className="grid gap-1.5 font-mono text-xs uppercase text-muted-foreground">
            prompt
            <textarea
              className="min-h-28 resize-y rounded-md border border-border bg-background px-3 py-2 font-mono text-sm normal-case leading-6 text-foreground outline-none transition placeholder:text-muted-foreground focus:border-primary"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Map architecture and explain runnable entry points"
            />
          </label>
          <div className="flex flex-wrap gap-2">
            <Button type="submit" disabled={!canSubmit}>
              {isSubmitting ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />
              ) : (
                <Play className="mr-2 h-4 w-4" aria-hidden="true" />
              )}
              Run
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                setRepoUrl(SAMPLE_REPO);
                setQuery(SAMPLE_QUERY);
                setCorrection("");
                setRun(null);
                onRunChange?.(null);
                setError(null);
              }}
            >
              <RotateCcw className="mr-2 h-4 w-4" aria-hidden="true" />
              Reset
            </Button>
            <Button type="button" variant="outline" disabled={!run || isRefreshing} onClick={() => void refreshRun()}>
              {isRefreshing ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />
              ) : (
                <RefreshCw className="mr-2 h-4 w-4" aria-hidden="true" />
              )}
              Refresh
            </Button>
          </div>
        </form>

        {error ? (
          <div className="flex gap-2 rounded-md border border-danger/30 bg-danger/10 p-3 text-sm leading-6 text-danger">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
            <span>{error}</span>
          </div>
        ) : null}

        {run ? (
          <div className="space-y-3 rounded-md border border-border bg-muted/60 p-3">
            <div className="grid gap-2 text-sm sm:grid-cols-2">
              <KeyValue label="Job" value={run.jobId.slice(0, 8)} />
              <KeyValue label="Agent" value={run.agentName} />
              <KeyValue label="Node" value={run.currentNode ?? "complete"} />
              <KeyValue label="Latency" value={formatSeconds(run.latency)} />
            </div>
            <div className="grid grid-cols-3 gap-2 text-sm">
              <ClaimCount label="Verified" value={run.verifiedCount} />
              <ClaimCount label="Unverified" value={run.unverifiedCount} />
              <ClaimCount label="Contradicted" value={run.contradictedCount} />
            </div>
            <form className="grid gap-2" onSubmit={submitRefine}>
              <label className="grid gap-1.5 font-mono text-xs uppercase text-muted-foreground">
                correction
                <input
                  className="h-10 rounded-md border border-border bg-background px-3 font-mono text-sm normal-case text-foreground outline-none transition placeholder:text-muted-foreground focus:border-primary"
                  value={correction}
                  onChange={(event) => setCorrection(event.target.value)}
                  placeholder="Focus on runtime entry points"
                />
              </label>
              <Button type="submit" disabled={!canRefine}>
                {isRefining ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />
                ) : (
                  <Send className="mr-2 h-4 w-4" aria-hidden="true" />
                )}
                Refine
              </Button>
            </form>
          </div>
        ) : (
          <div className="flex items-center gap-2 rounded-md border border-border bg-muted/50 p-3 font-mono text-sm text-muted-foreground">
            <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
            <span>Ready</span>
          </div>
        )}
      </div>
    </section>
  );
}

async function fetchRun(url: string, init?: RequestInit): Promise<ApiRunSummary> {
  const response = await fetch(url, {
    ...init,
    headers: { "content-type": "application/json" },
  });
  const payload = await response.json().catch(() => null);

  if (!response.ok) {
    throw new Error(detailFromPayload(payload) ?? response.statusText);
  }

  return payload as ApiRunSummary;
}

function detailFromPayload(payload: unknown): string | null {
  if (payload === null || typeof payload !== "object") {
    return null;
  }

  const detail = (payload as Record<string, unknown>).detail;
  if (typeof detail === "string") {
    return detail;
  }

  return null;
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Request failed.";
}

function statusVariant(status: RunStatus) {
  if (status === "completed") {
    return "success";
  }
  if (status === "failed") {
    return "danger";
  }
  return "warning";
}

function KeyValue({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="font-mono text-[10px] uppercase text-muted-foreground">{label}</p>
      <p className="mt-1 truncate font-mono text-xs font-medium">{value}</p>
    </div>
  );
}

function ClaimCount({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-md border border-border bg-background/70 p-2 text-center">
      <p className="font-mono text-lg font-semibold">{value}</p>
      <p className="mt-0.5 font-mono text-[10px] uppercase text-muted-foreground">{label}</p>
    </div>
  );
}
