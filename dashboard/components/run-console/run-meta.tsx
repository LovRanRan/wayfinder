import type { ReactNode } from "react";

export function RunMeta({ icon, label, value }: { icon: ReactNode; label: string; value: string }) {
  return (
    <div className="flex min-w-0 items-center gap-2 rounded-md border border-border bg-background/70 px-2.5 py-2">
      <span className="text-muted-foreground">{icon}</span>
      <span className="shrink-0 font-mono text-[10px] uppercase text-muted-foreground">{label}</span>
      <span className="truncate font-mono text-xs text-foreground">{value}</span>
    </div>
  );
}
