import { ExternalLink } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { RunSummary } from "@/lib/types";

type RunStatusTableProps = {
  runs: RunSummary[];
};

export function RunStatusTable({ runs }: RunStatusTableProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Recent runs</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[900px] border-collapse text-left text-sm">
            <thead>
              <tr className="border-b border-border text-xs uppercase text-muted-foreground">
                <th className="py-3 pr-4 font-medium">Repo</th>
                <th className="py-3 pr-4 font-medium">Intent</th>
                <th className="py-3 pr-4 font-medium">Status</th>
                <th className="py-3 pr-4 font-medium">Verified</th>
                <th className="py-3 pr-4 font-medium">Unverified</th>
                <th className="py-3 pr-4 font-medium">Contradicted</th>
                <th className="py-3 pr-4 font-medium">Trace</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <tr key={run.jobId} className="border-b border-border last:border-0">
                  <td className="py-3 pr-4 font-medium">{run.repoName}</td>
                  <td className="py-3 pr-4">{run.intent}</td>
                  <td className="py-3 pr-4">
                    <Badge variant={run.status === "completed" ? "success" : "warning"}>
                      {run.status}
                    </Badge>
                  </td>
                  <td className="py-3 pr-4">{run.verifiedCount}</td>
                  <td className="py-3 pr-4">{run.unverifiedCount}</td>
                  <td className="py-3 pr-4">{run.contradictedCount}</td>
                  <td className="py-3 pr-4">
                    <a
                      href={run.traceUrl}
                      className="inline-flex items-center gap-1 text-primary hover:underline"
                    >
                      Trace
                      <ExternalLink className="h-3 w-3" aria-hidden="true" />
                    </a>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}
