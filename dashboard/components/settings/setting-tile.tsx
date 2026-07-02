"use client";

import { KeyRound } from "lucide-react";

export function SettingTile({
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
