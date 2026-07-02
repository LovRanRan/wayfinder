import { Terminal } from "lucide-react";

export function WaitingOutput() {
  const rows = ["routing intent", "collecting evidence", "synthesizing answer", "checking labels"];

  return (
    <div className="rounded-md border border-primary/30 bg-primary/5 p-4">
      <div className="flex items-center gap-2 font-mono text-[11px] uppercase text-primary">
        <Terminal className="h-4 w-4" aria-hidden="true" />
        Waiting for answer
      </div>
      <div className="mt-4 grid gap-2 md:grid-cols-2">
        {rows.map((row, index) => (
          <div key={row} className="rounded-md border border-border bg-background/70 p-3">
            <div className="flex items-center justify-between gap-3">
              <span className="font-mono text-xs text-muted-foreground">{row}</span>
              <span className="h-2 w-2 animate-pulse rounded-full bg-primary" style={{ animationDelay: `${index * 120}ms` }} />
            </div>
            <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-muted">
              <div className="h-full w-1/2 animate-pulse rounded-full bg-primary/80" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
