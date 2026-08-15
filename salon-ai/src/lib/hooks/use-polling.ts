"use client";
import { useEffect, useRef, useState } from "react";

/** Polls `fetcher` on an interval and returns the latest data. Pauses when the tab is hidden. */
export function usePolling<T>(fetcher: () => Promise<T>, intervalMs: number, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const savedFetcher = useRef(fetcher);
  savedFetcher.current = fetcher;

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setInterval> | null = null;

    async function tick() {
      if (document.hidden) return;
      try {
        const result = await savedFetcher.current();
        if (!cancelled) setData(result);
      } catch {
        // transient network errors are fine to skip silently on a poll
      }
    }

    tick();
    timer = setInterval(tick, intervalMs);
    return () => {
      cancelled = true;
      if (timer) clearInterval(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return data;
}
