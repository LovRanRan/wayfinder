"use client";

import { FormEvent } from "react";
import {
  AlertTriangle,
  Bot,
  GitBranch,
  Loader2,
  RefreshCw,
  Send,
  User,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { CurrentRunConsole } from "@/components/current-run-console";
import { RunActivity } from "@/components/run-activity";
import { formatDate } from "@/lib/format";
import { runStatusVariant, threadStatusVariant } from "@/lib/workspace-format";
import type {
  ActiveRepoContext,
  ChatAnswerMode,
  DashboardRun,
  DashboardThread,
  DashboardThreadMessage,
} from "@/lib/types";

const answerModeHint: Record<ChatAnswerMode, string> = {
  auto: "Let Wayfinder pick the best response shape for your question.",
  conversation: "A short conversational answer.",
  report: "A structured grounded report with sections.",
  evidence: "Evidence-first: file:line citations and verification labels.",
  clarify: "Ask Wayfinder to clarify what it needs before running.",
};

type ChatPanelProps = {
  selectedThread: DashboardThread | null;
  activeContext: ActiveRepoContext | null;
  activeRun: DashboardRun | null;
  source: "api" | "demo";
  hasVisibleMessages: boolean;
  pendingUserMessage: string | null;
  error: string | null;
  statusMessage: string | null;
  chatDraft: string;
  answerMode: ChatAnswerMode;
  sendBlocker: string | null;
  canSend: boolean;
  isSending: boolean;
  isRefreshing: boolean;
  onChatDraftChange: (value: string) => void;
  onAnswerModeChange: (mode: ChatAnswerMode) => void;
  onSendChat: (event: FormEvent<HTMLFormElement>) => void;
  onRefreshThread: () => void;
  onSelectRun: (run: DashboardRun | null) => void;
};

export function ChatPanel({
  selectedThread,
  activeContext,
  activeRun,
  source,
  hasVisibleMessages,
  pendingUserMessage,
  error,
  statusMessage,
  chatDraft,
  answerMode,
  sendBlocker,
  canSend,
  isSending,
  isRefreshing,
  onChatDraftChange,
  onAnswerModeChange,
  onSendChat,
  onRefreshThread,
  onSelectRun,
}: ChatPanelProps) {
  return (
    <section className="grid min-h-0 grid-rows-[auto_1fr_auto] overflow-hidden rounded-lg border border-border bg-card">
      <header className="border-b border-border bg-muted/60 px-4 py-3">
        <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant={threadStatusVariant(selectedThread?.status ?? "active")}>
                {selectedThread?.status ?? "new"}
              </Badge>
              <Badge variant="outline">
                {activeContext?.repoName ?? selectedThread?.repoName ?? "ambient chat"}
              </Badge>
            </div>
            <h2 className="mt-2 truncate text-lg font-semibold">
              {selectedThread?.title ?? "Wayfinder repo workspace"}
            </h2>
            <p className="mt-1 truncate font-mono text-xs text-muted-foreground">
              {activeContext?.repoUrl ?? "Attach a repo by typing Open https://github.com/owner/repo"}
            </p>
          </div>
          <Button
            type="button"
            variant="outline"
            disabled={selectedThread === null || isRefreshing}
            onClick={onRefreshThread}
          >
            {isRefreshing ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />
            ) : (
              <RefreshCw className="mr-2 h-4 w-4" aria-hidden="true" />
            )}
            Refresh
          </Button>
        </div>
        {activeRun !== null ? (
          <div className="mt-3 rounded-md border border-border bg-background p-3">
            <RunActivity status={activeRun.status} startedAt={activeRun.createdAt} />
          </div>
        ) : null}
      </header>

      <div className="min-h-0 overflow-y-auto px-4 py-4">
        <div className="mx-auto grid max-w-4xl gap-3">
          {!hasVisibleMessages ? (
            <EmptyChatState
              hasActiveRepo={Boolean(activeContext?.repoUrl)}
              onPickPrompt={onChatDraftChange}
            />
          ) : (
            <>
              {selectedThread?.messages.map((message) => (
                <ThreadMessageRow
                  key={message.messageId}
                  message={message}
                  linkedRun={runFromMessage(selectedThread.runs, message)}
                  onSelectRun={onSelectRun}
                />
              ))}
              {pendingUserMessage !== null ? <PendingMessageRow content={pendingUserMessage} /> : null}
            </>
          )}

          {activeRun !== null ? (
            <details className="rounded-lg border border-border bg-background">
              <summary className="cursor-pointer px-4 py-3 text-sm font-semibold text-muted-foreground">
                Grounded report
              </summary>
              <div className="border-t border-border p-2">
                <CurrentRunConsole run={activeRun} source={source} embedded />
              </div>
            </details>
          ) : null}
        </div>
      </div>

      <div className="border-t border-border bg-muted/40 p-4">
        {error ? (
          <div className="mb-3 flex gap-2 rounded-md border border-danger/30 bg-danger/10 p-3 text-sm leading-6 text-danger">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
            <span>{error}</span>
          </div>
        ) : null}
        {statusMessage !== null && error === null ? (
          <div className="mb-3 flex gap-2 rounded-md border border-border bg-background p-3 text-sm leading-6 text-muted-foreground">
            {isSending ? (
              <Loader2 className="mt-0.5 h-4 w-4 shrink-0 animate-spin text-primary" aria-hidden="true" />
            ) : (
              <Bot className="mt-0.5 h-4 w-4 shrink-0 text-primary" aria-hidden="true" />
            )}
            <span>{statusMessage}</span>
          </div>
        ) : null}
        <form className="mx-auto grid max-w-4xl gap-2" onSubmit={onSendChat}>
          <textarea
            className="min-h-24 resize-y rounded-md border border-border bg-background px-3 py-2 text-sm leading-6 text-foreground outline-none transition placeholder:text-muted-foreground focus:border-primary"
            value={chatDraft}
            onChange={(event) => onChatDraftChange(event.target.value)}
            onKeyDown={(event) => {
              if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
                event.preventDefault();
                event.currentTarget.form?.requestSubmit();
              }
            }}
            placeholder={
              activeContext?.repoUrl
                ? "Ask naturally. Wayfinder will reuse the active repo context."
                : "Open https://github.com/owner/repo or ask what repo to inspect."
            }
          />
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex flex-wrap items-center gap-2">
              {(["auto", "conversation", "report", "evidence"] as ChatAnswerMode[]).map((mode) => (
                <button
                  key={mode}
                  type="button"
                  title={answerModeHint[mode]}
                  className={
                    answerMode === mode
                      ? "h-8 rounded-md bg-primary px-3 text-xs font-semibold text-primary-foreground"
                      : "h-8 rounded-md border border-border bg-background px-3 text-xs text-muted-foreground hover:text-foreground"
                  }
                  onClick={() => onAnswerModeChange(mode)}
                >
                  {mode}
                </button>
              ))}
            </div>
            <div className="flex items-center justify-between gap-3">
              <p className="text-[11px] leading-5 text-muted-foreground">
                {sendBlocker ?? "Ambient repo context and bounded memory are attached."}
              </p>
              <Button type="submit" disabled={!canSend}>
                {isSending ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />
                ) : (
                  <Send className="mr-2 h-4 w-4" aria-hidden="true" />
                )}
                {isSending ? "Sending" : "Send"}
              </Button>
            </div>
          </div>
        </form>
      </div>
    </section>
  );
}

function EmptyChatState({
  hasActiveRepo,
  onPickPrompt,
}: {
  hasActiveRepo: boolean;
  onPickPrompt: (value: string) => void;
}) {
  const prompts = hasActiveRepo
    ? [
        "Map the architecture and entry points",
        "How do I run this project?",
        "What are the main modules and how do they depend on each other?",
      ]
    : [
        "Open https://github.com/pallets/click and map the architecture",
        "Open https://github.com/tiangolo/fastapi",
      ];

  return (
    <div className="rounded-lg border border-dashed border-border bg-background p-6">
      <h3 className="text-heading font-semibold">
        {hasActiveRepo ? "Ask about this repo" : "Attach a repository to start"}
      </h3>
      <p className="mt-1 text-sm text-muted-foreground">
        {hasActiveRepo
          ? "Wayfinder grounds every answer in AST and repository evidence, and labels what it cannot verify."
          : "Paste a GitHub URL or say Use owner/repo. Try one of these:"}
      </p>
      <div className="mt-4 flex flex-wrap gap-2">
        {prompts.map((prompt) => (
          <button
            key={prompt}
            type="button"
            onClick={() => onPickPrompt(prompt)}
            className="rounded-full border border-border bg-card px-3 py-1.5 text-left text-xs text-foreground transition-colors hover:border-primary hover:bg-accent hover:text-accent-foreground"
          >
            {prompt}
          </button>
        ))}
      </div>
    </div>
  );
}

function ThreadMessageRow({
  message,
  linkedRun,
  onSelectRun,
}: {
  message: DashboardThreadMessage;
  linkedRun: DashboardRun | null;
  onSelectRun: (run: DashboardRun | null) => void;
}) {
  const Icon = message.role === "user" ? User : message.role === "assistant" ? Bot : GitBranch;
  return (
    <article
      className={
        message.role === "user"
          ? "ml-auto max-w-[86%] rounded-lg border border-primary/30 bg-primary/10 p-3"
          : "mr-auto max-w-[92%] rounded-lg border border-border bg-background p-3"
      }
    >
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <Icon className="h-4 w-4 text-primary" aria-hidden="true" />
        <span className="text-xs uppercase text-muted-foreground">{message.role}</span>
        <span className="text-[11px] text-muted-foreground">
          {formatDate(message.createdAt)}
        </span>
      </div>
      <div className="whitespace-pre-wrap break-words text-sm leading-6 text-foreground">
        {message.content}
      </div>
      {linkedRun !== null ? (
        <div className="mt-3 flex flex-wrap gap-2">
          <button type="button" onClick={() => onSelectRun(linkedRun)}>
            <Badge variant={runStatusVariant(linkedRun.status)}>run {linkedRun.status}</Badge>
          </button>
          <Badge variant="success">verified {message.verifiedCount}</Badge>
          <Badge variant="warning">unverified {message.unverifiedCount}</Badge>
          <Badge variant={message.contradictedCount > 0 ? "danger" : "outline"}>
            contradicted {message.contradictedCount}
          </Badge>
          {message.evidenceRefs.slice(0, 3).map((ref) => (
            <Badge key={ref} variant="outline">
              {ref}
            </Badge>
          ))}
        </div>
      ) : null}
    </article>
  );
}

function PendingMessageRow({ content }: { content: string }) {
  return (
    <article className="ml-auto max-w-[86%] rounded-lg border border-primary/40 bg-primary/10 p-3 opacity-80">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <User className="h-4 w-4 text-primary" aria-hidden="true" />
        <span className="text-xs uppercase text-muted-foreground">user</span>
        <Badge variant="warning">sending</Badge>
      </div>
      <div className="whitespace-pre-wrap break-words text-sm leading-6 text-foreground">
        {content}
      </div>
    </article>
  );
}

function runFromMessage(
  runs: DashboardRun[],
  message: DashboardThreadMessage,
): DashboardRun | null {
  if (message.sourceRunId === null) {
    return null;
  }
  return runs.find((run) => run.jobId === message.sourceRunId) ?? null;
}
