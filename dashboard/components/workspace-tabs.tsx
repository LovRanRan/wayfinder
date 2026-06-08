"use client";

import { BarChart3, History, MessageSquare, Play, Settings, Terminal } from "lucide-react";

export type WorkspaceTab = "threads" | "run" | "answer" | "history" | "metrics" | "settings";

type WorkspaceTabsProps = {
  activeTab: WorkspaceTab;
  onTabChange: (tab: WorkspaceTab) => void;
};

const tabs: { id: WorkspaceTab; label: string; icon: typeof Play }[] = [
  { id: "threads", label: "Threads", icon: MessageSquare },
  { id: "run", label: "Run", icon: Play },
  { id: "answer", label: "Answer", icon: Terminal },
  { id: "history", label: "History", icon: History },
  { id: "metrics", label: "Metrics", icon: BarChart3 },
  { id: "settings", label: "Settings", icon: Settings },
];

export function WorkspaceTabs({ activeTab, onTabChange }: WorkspaceTabsProps) {
  return (
    <nav className="grid grid-cols-2 gap-2 rounded-lg border border-border bg-card p-2 md:grid-cols-6">
      {tabs.map((tab) => {
        const Icon = tab.icon;
        const active = activeTab === tab.id;
        return (
          <button
            key={tab.id}
            type="button"
            className={
              active
                ? "flex h-11 items-center justify-center gap-2 rounded-md bg-primary px-3 font-mono text-sm font-medium text-primary-foreground"
                : "flex h-11 items-center justify-center gap-2 rounded-md border border-border bg-background px-3 font-mono text-sm text-muted-foreground hover:text-foreground"
            }
            onClick={() => onTabChange(tab.id)}
          >
            <Icon className="h-4 w-4" aria-hidden="true" />
            {tab.label}
          </button>
        );
      })}
    </nav>
  );
}
