"use client";

import { useState } from "react";
import { Loader2, LogOut, UserRound } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { DashboardUser } from "@/lib/types";

type WorkspaceAccountProps = {
  user: DashboardUser;
};

export function WorkspaceAccount({ user }: WorkspaceAccountProps) {
  const [isLoggingOut, setIsLoggingOut] = useState(false);

  async function logout() {
    setIsLoggingOut(true);
    await fetch("/api/wayfinder/auth/logout", { method: "POST" }).catch(() => null);
    window.location.reload();
  }

  return (
    <div className="flex flex-wrap items-center gap-3 rounded-lg border border-border bg-card px-4 py-3">
      <div className="flex h-10 w-10 items-center justify-center rounded-md border border-border bg-background text-primary">
        <UserRound className="h-5 w-5" aria-hidden="true" />
      </div>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-semibold">{user.displayName}</p>
        <p className="mt-1 truncate text-xs text-muted-foreground">workspace <span className="font-mono">@{user.workspaceId}</span></p>
      </div>
      <Button variant="outline" type="button" onClick={() => void logout()} disabled={isLoggingOut}>
        {isLoggingOut ? (
          <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />
        ) : (
          <LogOut className="mr-2 h-4 w-4" aria-hidden="true" />
        )}
        Logout
      </Button>
    </div>
  );
}
