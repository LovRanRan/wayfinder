"use client";

import { FormEvent, useEffect, useState } from "react";

import { RuntimeSettingsForm } from "@/components/settings/runtime-settings-form";
import { SandboxStatusCard } from "@/components/settings/sandbox-status-card";
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
      <RuntimeSettingsForm
        settings={settings}
        apiKey={apiKey}
        model={model}
        llmRouting={llmRouting}
        finalWriter={finalWriter}
        isLoading={isLoading}
        isSaving={isSaving}
        isClearing={isClearing}
        message={message}
        error={error}
        onSubmit={save}
        setApiKey={setApiKey}
        setModel={setModel}
        setLlmRouting={setLlmRouting}
        setFinalWriter={setFinalWriter}
        onClearKey={clearKey}
      />

      <SandboxStatusCard settings={settings} />
    </section>
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
