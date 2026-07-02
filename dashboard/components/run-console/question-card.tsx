import { BookOpenText } from "lucide-react";

export function QuestionCard({ query }: { query: string }) {
  return (
    <div className="rounded-md border border-border bg-muted/40 p-4">
      <div className="flex items-center gap-2 font-mono text-[11px] uppercase text-muted-foreground">
        <BookOpenText className="h-4 w-4 text-primary" aria-hidden="true" />
        Question
      </div>
      <p className="mt-3 text-sm font-medium leading-6 text-foreground">{query}</p>
    </div>
  );
}
