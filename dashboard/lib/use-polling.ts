"use client";

import { useEffect, useRef } from "react";

type PollController = {
  /** Schedule the next poll after delayMs; no-op once the effect is cleaned up. */
  schedule: (delayMs: number) => void;
  /** True once the effect is cleaned up; guards state updates after unmount. */
  isCancelled: () => boolean;
  /** Abort signal tied to the effect lifetime; pass to fetch(). */
  signal: AbortSignal;
};

/**
 * Run a self-scheduling poll loop tied to component lifetime.
 *
 * The callback decides its own cadence by calling `schedule(delayMs)` —
 * matching the existing dashboard pattern of variable backoff (fast while a
 * run is active, slower after an error). Cleanup cancels the pending timer and
 * aborts in-flight fetches so late responses can't touch unmounted state.
 * `enabled` gates the whole loop; `initialDelayMs` sets the first tick.
 */
export function usePolling(
  poll: (controller: PollController) => Promise<void>,
  { enabled, initialDelayMs }: { enabled: boolean; initialDelayMs: number },
): void {
  const pollRef = useRef(poll);
  pollRef.current = poll;

  useEffect(() => {
    if (!enabled) {
      return;
    }

    let cancelled = false;
    let timer: number | null = null;
    const abortController = new AbortController();

    const controller: PollController = {
      schedule: (delayMs: number) => {
        if (cancelled) {
          return;
        }
        timer = window.setTimeout(() => {
          void pollRef.current(controller);
        }, delayMs);
      },
      isCancelled: () => cancelled,
      signal: abortController.signal,
    };

    controller.schedule(initialDelayMs);

    return () => {
      cancelled = true;
      if (timer !== null) {
        window.clearTimeout(timer);
      }
      abortController.abort();
    };
    // The poll callback is intentionally read through a ref so a new closure
    // per render doesn't restart the loop; only these inputs restart it.
  }, [enabled, initialDelayMs]);
}
