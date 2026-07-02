"use client";

import { useState } from "react";
import { Archive, GitBranch, Link2, Loader2, Plus } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { formatDate } from "@/lib/format";
import { contextStatusVariant, threadStatusVariant } from "@/lib/workspace-format";
import type { ActiveRepoContext, DashboardThread } from "@/lib/types";

type ThreadRailProps = {
  activeContext: ActiveRepoContext | null;
  activeThreads: DashboardThread[];
  selectedThreadId: string | null;
  isClearingContext: boolean;
  archivingThreadId: string | null;
  isAttachingRepo: boolean;
  onAttachRepo: (repoRef: string) => void;
  onStartNewThread: () => void;
  onSelectThread: (thread: DashboardThread) => void;
  onArchiveThread: (thread: DashboardThread) => void;
};

export function ThreadRail({
  activeContext,
  activeThreads,
  selectedThreadId,
  isClearingContext,
  archivingThreadId,
  isAttachingRepo,
  onAttachRepo,
  onStartNewThread,
  onSelectThread,
  onArchiveThread,
}: ThreadRailProps) {
  const [repoDraft, setRepoDraft] = useState("");
  return (
    <aside className="grid min-h-0 grid-rows-[auto_1fr] gap-4">
      <section className="rounded-lg border border-border bg-card p-4">
        <div className="flex items-center gap-2 text-sm font-semibold">
          <GitBranch className="h-4 w-4 text-primary" aria-hidden="true" />
          Active repo
        </div>
        <div className="mt-3 rounded-md border border-border bg-background p-3">
          <div className="truncate font-mono text-sm font-semibold">
            {activeContext?.repoName ?? "No repo selected"}
          </div>
          <p className="mt-1 line-clamp-2 break-all font-mono text-[11px] leading-5 text-muted-foreground">
            {activeContext?.repoUrl ?? "Paste a GitHub URL or owner/repo in chat."}
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            <Badge variant={contextStatusVariant(activeContext?.status ?? "empty")}>
              {activeContext?.status ?? "empty"}
            </Badge>
            {activeContext?.activeFocus ? (
              <Badge variant="outline">{activeContext.activeFocus}</Badge>
            ) : null}
          </div>
        </div>
        <form
          className="mt-3 flex gap-2"
          onSubmit={(event) => {
            event.preventDefault();
            if (repoDraft.trim() === "" || isAttachingRepo) {
              return;
            }
            onAttachRepo(repoDraft);
            setRepoDraft("");
          }}
        >
          <input
            type="text"
            value={repoDraft}
            onChange={(event) => setRepoDraft(event.target.value)}
            placeholder="github.com/owner/repo"
            aria-label="Repository URL or owner/repo"
            className="h-9 min-w-0 flex-1 rounded-md border border-border bg-background px-3 font-mono text-xs text-foreground outline-none transition placeholder:text-muted-foreground focus:border-primary"
          />
          <Button type="submit" disabled={repoDraft.trim() === "" || isAttachingRepo}>
            {isAttachingRepo ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />
            ) : (
              <Link2 className="mr-2 h-4 w-4" aria-hidden="true" />
            )}
            Attach
          </Button>
        </form>
      </section>

      <section className="min-h-0 overflow-hidden rounded-lg border border-border bg-card">
        <header className="flex items-center justify-between gap-3 border-b border-border bg-muted/60 px-4 py-3">
          <div className="text-sm font-semibold">Repo threads</div>
          <div className="flex items-center gap-2">
            <Badge variant="outline">{activeThreads.length}</Badge>
            <Button
              type="button"
              variant="outline"
              disabled={isClearingContext}
              onClick={onStartNewThread}
            >
              {isClearingContext ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />
              ) : (
                <Plus className="mr-2 h-4 w-4" aria-hidden="true" />
              )}
              New
            </Button>
          </div>
        </header>
        <div className="max-h-full overflow-y-auto p-2">
          {activeThreads.length === 0 ? (
            <div className="rounded-md border border-border bg-muted/50 p-3 text-xs leading-5 text-muted-foreground">
              Start by typing a repo URL in chat.
            </div>
          ) : (
            activeThreads.map((thread) => (
              <div
                key={thread.threadId}
                className={
                  thread.threadId === selectedThreadId
                    ? "flex w-full items-start gap-2 rounded-md border border-primary bg-primary/10 p-3"
                    : "flex w-full items-start gap-2 rounded-md border border-transparent p-3 hover:border-border hover:bg-muted/50"
                }
              >
                <button
                  type="button"
                  className="min-w-0 flex-1 text-left"
                  onClick={() => onSelectThread(thread)}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="min-w-0 truncate text-sm font-medium">
                      {thread.title}
                    </span>
                    <Badge variant={threadStatusVariant(thread.status)}>{thread.status}</Badge>
                  </div>
                  <div className="mt-2 truncate font-mono text-xs text-muted-foreground">
                    {thread.repoName}
                  </div>
                  <div className="mt-1 text-[11px] text-muted-foreground">
                    {thread.messages.length} messages · {formatDate(thread.updatedAt)}
                  </div>
                </button>
                <button
                  type="button"
                  className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-border bg-background text-muted-foreground hover:text-foreground disabled:opacity-50"
                  title={`Archive ${thread.title}`}
                  aria-label={`Archive ${thread.title}`}
                  disabled={archivingThreadId === thread.threadId || thread.status === "running"}
                  onClick={() => onArchiveThread(thread)}
                >
                  {archivingThreadId === thread.threadId ? (
                    <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                  ) : (
                    <Archive className="h-4 w-4" aria-hidden="true" />
                  )}
                </button>
              </div>
            ))
          )}
        </div>
      </section>
    </aside>
  );
}
