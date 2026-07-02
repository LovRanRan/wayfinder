"use client";

import { ShieldAlert, SlidersHorizontal } from "lucide-react";

import { SettingTile } from "@/components/settings/setting-tile";
import type { WorkspaceSettings } from "@/lib/types";

type SandboxStatusCardProps = {
  settings: WorkspaceSettings | null;
};

export function SandboxStatusCard({ settings }: SandboxStatusCardProps) {
  return (
    <section className="overflow-hidden rounded-lg border border-border bg-card">
      <header className="border-b border-border bg-muted/60 px-4 py-3">
        <div className="flex items-center gap-2 text-sm font-semibold">
          <ShieldAlert className="h-4 w-4 text-primary" aria-hidden="true" />
          Verification sandbox
        </div>
        <p className="mt-1 text-xs text-muted-foreground">test runner policy · public boundary</p>
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
          tone={sandboxTone(settings?.sandboxStatus)}
        />
        <div className="rounded-md border border-border bg-muted/40 p-4">
          <p className="text-xs leading-6 text-muted-foreground">
            {settings?.sandboxMessage ?? "Loading sandbox policy."}
          </p>
        </div>
      </div>
    </section>
  );
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
