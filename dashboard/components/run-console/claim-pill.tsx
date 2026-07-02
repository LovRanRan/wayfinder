import { AlertTriangle, CheckCircle2 } from "lucide-react";

export function ClaimPill({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: "success" | "warning" | "danger";
}) {
  const Icon = tone === "success" ? CheckCircle2 : AlertTriangle;
  return (
    <div className="rounded-md border border-border bg-muted/60 px-3 py-2">
      <div className="flex items-center gap-2">
        <Icon className={claimIconClass(tone)} aria-hidden="true" />
        <span className="font-mono text-lg font-semibold">{value}</span>
      </div>
      <div className="mt-1 font-mono text-[10px] uppercase text-muted-foreground">{label}</div>
    </div>
  );
}

function claimIconClass(tone: "success" | "warning" | "danger") {
  const base = "h-4 w-4";
  if (tone === "success") {
    return `${base} text-success`;
  }
  if (tone === "warning") {
    return `${base} text-warning`;
  }
  return `${base} text-danger`;
}
