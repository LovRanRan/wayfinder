"use client";

import { FormEvent, useEffect, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  KeyRound,
  Loader2,
  Save,
  ShieldAlert,
  SlidersHorizontal,
  Trash2,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type {
  ApiWorkspaceSettings,
  WorkspaceFinalWriter,
  WorkspaceLLMRouting,
  WorkspaceSettings,
} from "@/lib/types";

export function WorkspaceSettingsPanel() {
  const [settings, setSettings] = useState<WorkspaceSettings | null>(null);
  const [apiKey, setApiKey] = useState("");
  const [model, setModel] = useState("gpt-5.5");
  const [llmRouting, setLlmRouting] = useState<WorkspaceLLMRouting>("off");
  const [finalWriter, setFinalWriter] = useState<WorkspaceFinalWriter>("deterministic");
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isClearing, setIsClearing] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function loadSettings() {
      setIsLoading(true);
      setError(null);
      try {
        const nextSettings = await fetchSettings();
        if (cancelled) {
          return;
        }
        applySettings(nextSettings);
      } catch (settingsError) {
        if (!cancelled) {
          setError(errorMessage(settingsError));
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }

    void loadSettings();
    return () => {
      cancelled = true;
    };
  }, []);

  function applySettings(nextSettings: WorkspaceSettings) {
    setSettings(nextSettings);
    setModel(nextSettings.openaiModel);
    setLlmRouting(nextSettings.llmRouting);
    setFinalWriter(nextSettings.finalWriter);
    setApiKey("");
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSaving(true);
    setMessage(null);
    setError(null);

    try {
      const body: Record<string, unknown> = {
        openai_model: model.trim(),
        llm_routing: llmRouting,
        final_writer: finalWriter,
      };
      if (apiKey.trim()) {
        body.openai_api_key = apiKey.trim();
      }
      const nextSettings = await fetchSettings({
        method: "PUT",
        body: JSON.stringify(body),
      });
      applySettings(nextSettings);
      setMessage("Workspace runtime settings saved.");
    } catch (saveError) {
      setError(errorMessage(saveError));
    } finally {
      setIsSaving(false);
    }
  }

  async function clearKey() {
    setIsClearing(true);
    setMessage(null);
    setError(null);

    try {
      const nextSettings = await fetchSettings({
        method: "PUT",
        body: JSON.stringify({ clear_openai_api_key: true }),
      });
      applySettings(nextSettings);
      setMessage("Workspace API key cleared.");
    } catch (clearError) {
      setError(errorMessage(clearError));
    } finally {
      setIsClearing(false);
    }
  }

  return (
    <section className="grid gap-4 xl:grid-cols-[minmax(0,1.15fr)_minmax(320px,0.85fr)]">
      <form className="overflow-hidden rounded-lg border border-border bg-card" onSubmit={save}>
        <header className="flex flex-wrap items-center justify-between gap-3 border-b border-border bg-muted/60 px-4 py-3">
          <div>
            <div className="flex items-center gap-2 font-mono text-sm font-semibold">
              <SlidersHorizontal className="h-4 w-4 text-primary" aria-hidden="true" />
              Runtime settings
            </div>
            <p className="mt-1 font-mono text-xs text-muted-foreground">
              workspace provider · routing · synthesis
            </p>
          </div>
          {settings ? (
            <Badge variant={settings.openaiKeyConfigured ? "success" : "warning"}>
              {settings.openaiKeyConfigured ? "key configured" : "key missing"}
            </Badge>
          ) : null}
        </header>

        <div className="grid gap-4 p-4">
          {isLoading ? <LoadingPanel /> : null}

          <div className="grid gap-3 md:grid-cols-2">
            <label className="grid gap-1.5 font-mono text-xs uppercase text-muted-foreground">
              OpenAI key
              <input
                className="h-10 rounded-md border border-border bg-background px-3 font-mono text-sm normal-case text-foreground outline-none transition placeholder:text-muted-foreground focus:border-primary"
                value={apiKey}
                onChange={(event) => setApiKey(event.target.value)}
                placeholder={settings?.openaiKeyLabel ?? "sk-..."}
                type="password"
                autoComplete="off"
              />
            </label>
            <label className="grid gap-1.5 font-mono text-xs uppercase text-muted-foreground">
              Model
              <input
                className="h-10 rounded-md border border-border bg-background px-3 font-mono text-sm normal-case text-foreground outline-none transition placeholder:text-muted-foreground focus:border-primary"
                value={model}
                onChange={(event) => setModel(event.target.value)}
                placeholder="gpt-5.5"
              />
            </label>
            <label className="grid gap-1.5 font-mono text-xs uppercase text-muted-foreground">
              Routing
              <select
                className="h-10 rounded-md border border-border bg-background px-3 font-mono text-sm normal-case text-foreground outline-none transition focus:border-primary"
                value={llmRouting}
                onChange={(event) => setLlmRouting(event.target.value as WorkspaceLLMRouting)}
              >
                <option value="off">off</option>
                <option value="openai">openai</option>
              </select>
            </label>
            <label className="grid gap-1.5 font-mono text-xs uppercase text-muted-foreground">
              Final writer
              <select
                className="h-10 rounded-md border border-border bg-background px-3 font-mono text-sm normal-case text-foreground outline-none transition focus:border-primary"
                value={finalWriter}
                onChange={(event) => setFinalWriter(event.target.value as WorkspaceFinalWriter)}
              >
                <option value="deterministic">deterministic</option>
                <option value="openai">openai</option>
              </select>
            </label>
          </div>

          <div className="grid gap-3 md:grid-cols-3">
            <SettingTile
              icon={KeyRound}
              label="key"
              value={settings?.openaiKeyLabel ?? "not configured"}
              tone={settings?.openaiKeyConfigured ? "success" : "warning"}
            />
            <SettingTile icon={SlidersHorizontal} label="routing" value={llmRouting} tone="muted" />
            <SettingTile icon={CheckCircle2} label="writer" value={finalWriter} tone="muted" />
          </div>

          {message ? <InlineNotice tone="success" message={message} /> : null}
          {error ? <InlineNotice tone="danger" message={error} /> : null}

          <div className="flex flex-wrap gap-2">
            <Button type="submit" disabled={isSaving || model.trim().length === 0}>
              {isSaving ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />
              ) : (
                <Save className="mr-2 h-4 w-4" aria-hidden="true" />
              )}
              Save
            </Button>
            <Button
              type="button"
              variant="outline"
              disabled={isClearing || !settings?.openaiKeyConfigured}
              onClick={() => void clearKey()}
            >
              {isClearing ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />
              ) : (
                <Trash2 className="mr-2 h-4 w-4" aria-hidden="true" />
              )}
              Clear key
            </Button>
          </div>
        </div>
      </form>

      <section className="overflow-hidden rounded-lg border border-border bg-card">
        <header className="border-b border-border bg-muted/60 px-4 py-3">
          <div className="flex items-center gap-2 font-mono text-sm font-semibold">
            <ShieldAlert className="h-4 w-4 text-primary" aria-hidden="true" />
            Verification sandbox
          </div>
          <p className="mt-1 font-mono text-xs text-muted-foreground">test runner policy · public boundary</p>
        </header>
        <div className="grid gap-3 p-4">
          <SettingTile
            icon={ShieldAlert}
            label="sandbox"
            value={settings?.sandboxStatus ?? "loading"}
            tone={sandboxTone(settings?.sandboxStatus)}
          />
          <SettingTile
            icon={SlidersHorizontal}
            label="verifier"
            value={settings?.verifierRunner ?? "placeholder"}
            tone="muted"
          />
          <div className="rounded-md border border-border bg-muted/40 p-4">
            <p className="font-mono text-xs leading-6 text-muted-foreground">
              {settings?.sandboxMessage ?? "Loading sandbox policy."}
            </p>
          </div>
        </div>
      </section>
    </section>
  );
}

function LoadingPanel() {
  return (
    <div className="grid gap-2 rounded-md border border-border bg-muted/40 p-4">
      <div className="flex items-center gap-2 font-mono text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
        Loading workspace settings
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-background">
        <div className="h-full w-1/2 animate-pulse rounded-full bg-primary/80" />
      </div>
    </div>
  );
}

function SettingTile({
  icon: Icon,
  label,
  value,
  tone,
}: {
  icon: typeof KeyRound;
  label: string;
  value: string;
  tone: "muted" | "success" | "warning" | "danger";
}) {
  return (
    <div className="rounded-md border border-border bg-muted/40 p-3">
      <div className="flex items-center gap-2">
        <Icon className={tileIconClass(tone)} aria-hidden="true" />
        <span className="font-mono text-[10px] uppercase text-muted-foreground">{label}</span>
      </div>
      <p className="mt-2 truncate font-mono text-sm font-semibold text-foreground">{value}</p>
    </div>
  );
}

function InlineNotice({ tone, message }: { tone: "success" | "danger"; message: string }) {
  const Icon = tone === "success" ? CheckCircle2 : AlertTriangle;
  return (
    <div className={tone === "success" ? noticeClass("success") : noticeClass("danger")}>
      <Icon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
      <span>{message}</span>
    </div>
  );
}

async function fetchSettings(init?: RequestInit): Promise<WorkspaceSettings> {
  const response = await fetch("/api/wayfinder/workspace/settings", {
    ...init,
    headers: { "content-type": "application/json" },
  });
  const payload = await response.json().catch(() => null);

  if (!response.ok) {
    throw new Error(detailFromPayload(payload) ?? response.statusText);
  }

  return toWorkspaceSettings(payload as ApiWorkspaceSettings);
}

function toWorkspaceSettings(settings: ApiWorkspaceSettings): WorkspaceSettings {
  return {
    workspaceId: settings.workspace_id,
    displayName: settings.display_name,
    openaiKeyConfigured: settings.openai_key_configured,
    openaiKeyLabel: settings.openai_key_label,
    openaiModel: settings.openai_model,
    llmRouting: settings.llm_routing,
    finalWriter: settings.final_writer,
    verifierRunner: settings.verifier_runner,
    sandboxStatus: settings.sandbox_status,
    sandboxMessage: settings.sandbox_message,
  };
}

function detailFromPayload(payload: unknown): string | null {
  if (payload !== null && typeof payload === "object" && "detail" in payload) {
    const detail = (payload as { detail?: unknown }).detail;
    return typeof detail === "string" ? detail : null;
  }
  return null;
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Request failed.";
}

function sandboxTone(status: WorkspaceSettings["sandboxStatus"] | undefined) {
  if (status === "enabled") {
    return "success";
  }
  if (status === "unavailable") {
    return "warning";
  }
  return "muted";
}

function tileIconClass(tone: "muted" | "success" | "warning" | "danger") {
  const base = "h-4 w-4";
  if (tone === "success") {
    return `${base} text-success`;
  }
  if (tone === "warning") {
    return `${base} text-warning`;
  }
  if (tone === "danger") {
    return `${base} text-danger`;
  }
  return `${base} text-muted-foreground`;
}

function noticeClass(tone: "success" | "danger") {
  const base = "flex gap-2 rounded-md border p-3 text-sm leading-6";
  if (tone === "success") {
    return `${base} border-success/30 bg-success/10 text-success`;
  }
  return `${base} border-danger/30 bg-danger/10 text-danger`;
}
