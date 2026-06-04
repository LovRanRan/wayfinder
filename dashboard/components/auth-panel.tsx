"use client";

import { FormEvent, useState } from "react";
import { KeyRound, Loader2, LogIn, UserPlus } from "lucide-react";

import { Button } from "@/components/ui/button";

type AuthMode = "login" | "register";

export function AuthPanel() {
  const [mode, setMode] = useState<AuthMode>("login");
  const [workspaceId, setWorkspaceId] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    setError(null);

    try {
      const response = await fetch(`/api/wayfinder/auth/${mode}`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          workspace_id: workspaceId,
          display_name: displayName,
          password,
        }),
      });
      const payload = await response.json().catch(() => null);
      if (!response.ok) {
        throw new Error(detailFromPayload(payload) ?? response.statusText);
      }
      window.location.reload();
    } catch (authError) {
      setError(authError instanceof Error ? authError.message : "Authentication failed.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <section className="grid min-h-[560px] overflow-hidden rounded-lg border border-border bg-card lg:grid-cols-[0.9fr_1.1fr]">
      <div className="border-b border-border bg-muted/50 p-6 lg:border-b-0 lg:border-r">
        <div className="flex h-full flex-col justify-between gap-8">
          <div>
            <div className="inline-flex h-10 w-10 items-center justify-center rounded-md border border-border bg-background text-primary">
              <KeyRound className="h-5 w-5" aria-hidden="true" />
            </div>
            <h1 className="mt-5 font-mono text-2xl font-semibold">wayfinder workspace</h1>
            <p className="mt-3 max-w-lg text-sm leading-6 text-muted-foreground">
              Sign in to keep repository analysis, verification labels, and refine history separated from other users.
            </p>
          </div>
          <div className="grid gap-3 font-mono text-xs text-muted-foreground">
            <div className="rounded-md border border-border bg-background/70 p-3">
              Public GitHub repos can be analyzed after login when ingestion is enabled.
            </div>
            <div className="rounded-md border border-border bg-background/70 p-3">
              OpenAI usage is controlled by deployment/user key policy; run history never stores raw API keys.
            </div>
          </div>
        </div>
      </div>

      <form className="grid content-center gap-4 p-6" onSubmit={submit}>
        <div className="inline-grid grid-cols-2 rounded-md border border-border bg-background p-1">
          <button
            type="button"
            className={modeButtonClass(mode === "login")}
            onClick={() => setMode("login")}
          >
            Login
          </button>
          <button
            type="button"
            className={modeButtonClass(mode === "register")}
            onClick={() => setMode("register")}
          >
            Register
          </button>
        </div>

        <label className="grid gap-1.5 font-mono text-xs uppercase text-muted-foreground">
          workspace id
          <input
            className="h-11 rounded-md border border-border bg-background px-3 font-mono text-sm normal-case text-foreground outline-none transition placeholder:text-muted-foreground focus:border-primary"
            value={workspaceId}
            onChange={(event) => setWorkspaceId(event.target.value)}
            placeholder="github-handle-or-team"
            autoComplete="username"
          />
        </label>

        {mode === "register" ? (
          <label className="grid gap-1.5 font-mono text-xs uppercase text-muted-foreground">
            display name
            <input
              className="h-11 rounded-md border border-border bg-background px-3 font-mono text-sm normal-case text-foreground outline-none transition placeholder:text-muted-foreground focus:border-primary"
              value={displayName}
              onChange={(event) => setDisplayName(event.target.value)}
              placeholder="Haichuan"
              autoComplete="name"
            />
          </label>
        ) : null}

        <label className="grid gap-1.5 font-mono text-xs uppercase text-muted-foreground">
          password
          <input
            className="h-11 rounded-md border border-border bg-background px-3 font-mono text-sm normal-case text-foreground outline-none transition placeholder:text-muted-foreground focus:border-primary"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="8+ characters"
            type="password"
            autoComplete={mode === "login" ? "current-password" : "new-password"}
          />
        </label>

        {error ? (
          <div className="rounded-md border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger">
            {error}
          </div>
        ) : null}

        <Button type="submit" disabled={!canSubmit(mode, workspaceId, displayName, password) || isSubmitting}>
          {isSubmitting ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />
          ) : mode === "login" ? (
            <LogIn className="mr-2 h-4 w-4" aria-hidden="true" />
          ) : (
            <UserPlus className="mr-2 h-4 w-4" aria-hidden="true" />
          )}
          {mode === "login" ? "Login" : "Create workspace"}
        </Button>
      </form>
    </section>
  );
}

function canSubmit(mode: AuthMode, workspaceId: string, displayName: string, password: string) {
  if (workspaceId.trim().length === 0 || password.length < 8) {
    return false;
  }
  return mode === "login" || displayName.trim().length > 0;
}

function modeButtonClass(active: boolean) {
  return active
    ? "rounded-sm bg-primary px-3 py-2 font-mono text-xs font-medium text-primary-foreground"
    : "rounded-sm px-3 py-2 font-mono text-xs text-muted-foreground hover:text-foreground";
}

function detailFromPayload(payload: unknown): string | null {
  if (payload === null || typeof payload !== "object") {
    return null;
  }
  const detail = (payload as Record<string, unknown>).detail;
  return typeof detail === "string" ? detail : null;
}
