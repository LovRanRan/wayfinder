"use client";

import type { FormEvent } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  KeyRound,
  Loader2,
  Save,
  SlidersHorizontal,
  Trash2,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { SettingTile } from "@/components/settings/setting-tile";
import type {
  WorkspaceFinalWriter,
  WorkspaceLLMRouting,
  WorkspaceSettings,
} from "@/lib/types";

type RuntimeSettingsFormProps = {
  settings: WorkspaceSettings | null;
  apiKey: string;
  model: string;
  llmRouting: WorkspaceLLMRouting;
  finalWriter: WorkspaceFinalWriter;
  isLoading: boolean;
  isSaving: boolean;
  isClearing: boolean;
  message: string | null;
  error: string | null;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void | Promise<void>;
  setApiKey: (value: string) => void;
  setModel: (value: string) => void;
  setLlmRouting: (value: WorkspaceLLMRouting) => void;
  setFinalWriter: (value: WorkspaceFinalWriter) => void;
  onClearKey: () => Promise<void>;
};

export function RuntimeSettingsForm({
  settings,
  apiKey,
  model,
  llmRouting,
  finalWriter,
  isLoading,
  isSaving,
  isClearing,
  message,
  error,
  onSubmit,
  setApiKey,
  setModel,
  setLlmRouting,
  setFinalWriter,
  onClearKey,
}: RuntimeSettingsFormProps) {
  return (
    <form className="overflow-hidden rounded-lg border border-border bg-card" onSubmit={onSubmit}>
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
            onClick={() => void onClearKey()}
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

function InlineNotice({ tone, message }: { tone: "success" | "danger"; message: string }) {
  const Icon = tone === "success" ? CheckCircle2 : AlertTriangle;
  return (
    <div className={tone === "success" ? noticeClass("success") : noticeClass("danger")}>
      <Icon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
      <span>{message}</span>
    </div>
  );
}

function noticeClass(tone: "success" | "danger") {
  const base = "flex gap-2 rounded-md border p-3 text-sm leading-6";
  if (tone === "success") {
    return `${base} border-success/30 bg-success/10 text-success`;
  }
  return `${base} border-danger/30 bg-danger/10 text-danger`;
}
