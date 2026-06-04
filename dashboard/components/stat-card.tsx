import type { LucideIcon } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

type StatCardProps = {
  icon: LucideIcon;
  label: string;
  value: string;
  detail: string;
};

export function StatCard({ icon: Icon, label, value, detail }: StatCardProps) {
  return (
    <Card className="bg-card/95">
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="font-mono text-xs font-medium uppercase text-muted-foreground">{label}</CardTitle>
        <Icon className="h-4 w-4 text-primary" aria-hidden="true" />
      </CardHeader>
      <CardContent>
        <div className="font-mono text-2xl font-semibold">{value}</div>
        <p className="mt-1 font-mono text-[11px] text-muted-foreground">{detail}</p>
      </CardContent>
    </Card>
  );
}
