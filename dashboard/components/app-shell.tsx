"use client";

import Link from "next/link";
import { BarChart3, Compass, ExternalLink, History, MessageSquare, Settings } from "lucide-react";

import { WorkspaceAccount } from "@/components/workspace-account";
import { Badge } from "@/components/ui/badge";
import { ToastProvider } from "@/components/ui/toast";
import type { DashboardUser } from "@/lib/types";

export type AppSection = "threads" | "history" | "metrics" | "settings";

const navItems: { id: AppSection; label: string; href: string; icon: typeof MessageSquare }[] = [
  { id: "threads", label: "Threads", href: "/", icon: MessageSquare },
  { id: "history", label: "History", href: "/history", icon: History },
  { id: "metrics", label: "Metrics", href: "/metrics", icon: BarChart3 },
  { id: "settings", label: "Settings", href: "/settings", icon: Settings },
];

type AppShellProps = {
  active: AppSection;
  user: DashboardUser;
  source: "api" | "demo";
  publicApiBaseUrl: string;
  /** Threads uses a bounded full-height chat layout; other pages scroll. */
  contentScroll?: boolean;
  children: React.ReactNode;
};

export function AppShell({
  active,
  user,
  source,
  publicApiBaseUrl,
  contentScroll = true,
  children,
}: AppShellProps) {
  const activeLabel = navItems.find((item) => item.id === active)?.label ?? "Workspace";

  return (
    <ToastProvider>
    <div className="flex h-screen overflow-hidden bg-background text-foreground">
      <aside className="hidden w-60 shrink-0 flex-col border-r border-border bg-card md:flex">
        <div className="flex items-center gap-2 border-b border-border px-5 py-4">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <Compass className="h-4 w-4" aria-hidden="true" />
          </div>
          <div>
            <div className="text-sm font-semibold tracking-tight">Wayfinder</div>
            <div className="text-[11px] text-muted-foreground">Codebase onboarding</div>
          </div>
        </div>
        <nav className="flex flex-1 flex-col gap-1 p-3" aria-label="Primary">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = item.id === active;
            return (
              <Link
                key={item.id}
                href={item.href}
                aria-current={isActive ? "page" : undefined}
                className={
                  isActive
                    ? "flex items-center gap-3 rounded-md bg-accent px-3 py-2 text-sm font-medium text-accent-foreground"
                    : "flex items-center gap-3 rounded-md px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                }
              >
                <Icon className="h-4 w-4" aria-hidden="true" />
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="border-t border-border p-3">
          <a
            href={`${publicApiBaseUrl}/docs`}
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-3 rounded-md px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          >
            <ExternalLink className="h-4 w-4" aria-hidden="true" />
            API docs
          </a>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex shrink-0 flex-wrap items-center justify-between gap-3 border-b border-border bg-card px-4 py-3 md:px-6">
          <div className="flex items-center gap-3">
            <span className="text-heading font-semibold md:hidden">Wayfinder</span>
            <nav aria-label="Breadcrumb" className="hidden items-center gap-2 text-sm md:flex">
              <span className="text-muted-foreground">Workspace</span>
              <span className="text-muted-foreground">/</span>
              <span className="font-medium">{activeLabel}</span>
            </nav>
            <Badge variant={source === "api" ? "success" : "warning"}>
              {source === "api" ? "Live API" : "Sample data"}
            </Badge>
          </div>
          <div className="flex items-center gap-2">
            <WorkspaceAccount user={user} />
          </div>
        </header>

        <nav
          className="flex shrink-0 gap-1 overflow-x-auto border-b border-border bg-card px-2 py-1.5 md:hidden"
          aria-label="Primary mobile"
        >
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = item.id === active;
            return (
              <Link
                key={item.id}
                href={item.href}
                aria-current={isActive ? "page" : undefined}
                className={
                  isActive
                    ? "flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-xs font-medium text-accent-foreground"
                    : "flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs text-muted-foreground"
                }
              >
                <Icon className="h-3.5 w-3.5" aria-hidden="true" />
                {item.label}
              </Link>
            );
          })}
        </nav>

        <main
          className={
            contentScroll
              ? "min-h-0 flex-1 overflow-y-auto px-4 py-4 md:px-6"
              : "flex min-h-0 flex-1 flex-col overflow-hidden px-4 py-4 md:px-6"
          }
        >
          {children}
        </main>
      </div>
    </div>
    </ToastProvider>
  );
}
