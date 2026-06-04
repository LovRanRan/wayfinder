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
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatSeconds, toDashboardRun } from "@/lib/metrics";
import type { ApiRunSummary, DashboardRun, RunStatus } from "@/lib/types";

const SAMPLE_REPO = ".";
const SAMPLE_QUERY = "Map this repo architecture";
const terminalStatuses: RunStatus[] = ["completed", "failed"];

export function RunLauncher() {
  const [repoUrl, setRepoUrl] = useState(SAMPLE_REPO);
  const [query, setQuery] = useState(SAMPLE_QUERY);
  const [correction, setCorrection] = useState("");
  const [run, setRun] = useState<DashboardRun | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isRefining, setIsRefining] = useState(false);

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
        setRun(toDashboardRun(payload));
      } catch (refreshError) {
        setError(errorMessage(refreshError));
      } finally {
        if (!silent) {
          setIsRefreshing(false);
        }
      }
    },
    [run],
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
      setRun(toDashboardRun(payload));
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
      setRun(toDashboardRun(payload));
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
    <Card>
      <CardHeader className="flex flex-row items-start justify-between gap-3">
        <CardTitle className="flex items-center gap-2">
          <Play className="h-4 w-4" aria-hidden="true" />
          Try a run
        </CardTitle>
        {run ? <Badge variant={statusVariant(run.status)}>{run.status}</Badge> : null}
      </CardHeader>
      <CardContent className="space-y-4">
        <form className="grid gap-3" onSubmit={submitRun}>
          <label className="grid gap-1.5 text-sm font-medium">
            Repo URL or local path
            <input
              className="h-10 rounded-md border border-border bg-background px-3 text-sm font-normal outline-none transition focus:border-primary"
              value={repoUrl}
              onChange={(event) => setRepoUrl(event.target.value)}
              placeholder="."
            />
          </label>
          <label className="grid gap-1.5 text-sm font-medium">
            Question
            <textarea
              className="min-h-24 resize-y rounded-md border border-border bg-background px-3 py-2 text-sm font-normal leading-6 outline-none transition focus:border-primary"
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
          <div className="space-y-3 rounded-md border border-border bg-muted p-3">
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
            <div className="max-h-40 overflow-y-auto rounded-md border border-border bg-card p-3 text-sm leading-6">
              {run.finalOutput ?? run.error ?? "Run is still producing output."}
            </div>
            <form className="grid gap-2" onSubmit={submitRefine}>
              <label className="grid gap-1.5 text-sm font-medium">
                Correction
                <input
                  className="h-10 rounded-md border border-border bg-background px-3 text-sm font-normal outline-none transition focus:border-primary"
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
          <div className="flex items-center gap-2 rounded-md border border-border p-3 text-sm text-muted-foreground">
            <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
            <span>Ready</span>
          </div>
        )}
      </CardContent>
    </Card>
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
      <p className="text-xs uppercase text-muted-foreground">{label}</p>
      <p className="mt-1 truncate font-medium">{value}</p>
    </div>
  );
}

function ClaimCount({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-md border border-border bg-card p-2 text-center">
      <p className="text-lg font-semibold">{value}</p>
      <p className="mt-0.5 text-xs text-muted-foreground">{label}</p>
    </div>
  );
}
