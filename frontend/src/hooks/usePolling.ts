import { useEffect, useRef } from "preact/hooks";

/**
 * Calls ``fn`` now and then every ``intervalMs`` using chained timeouts. Pauses while the
 * page is hidden and refreshes immediately on return if the data is older than the interval.
 *
 * Exactly one loop runs per mount: a single timer handle is always cleared before it is
 * re-armed, and visibility changes are ignored while a tick is in flight (that tick re-arms
 * the timer itself when it settles, if the page is visible then).
 */
export function usePolling(fn: () => Promise<void>, intervalMs: number, deps: readonly unknown[]) {
  const last = useRef(0);

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | undefined;
    let cancelled = false;
    let inFlight = false;

    const schedule = (ms: number) => {
      clearTimeout(timer);
      timer = setTimeout(() => void tick(), ms);
    };

    const tick = async () => {
      if (cancelled || inFlight) return;
      clearTimeout(timer);
      timer = undefined;
      inFlight = true;
      last.current = Date.now();
      try {
        await fn();
      } catch {
        // ``fn`` owns its error handling; a rejection must not kill the loop.
      } finally {
        inFlight = false;
      }
      if (!cancelled && document.visibilityState === "visible") schedule(intervalMs);
    };

    const onVisibility = () => {
      if (inFlight) return; // the running tick decides what comes next
      clearTimeout(timer);
      timer = undefined;
      if (document.visibilityState !== "visible") return;
      const age = Date.now() - last.current;
      if (age >= intervalMs) void tick();
      else schedule(intervalMs - age);
    };

    void tick();
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      cancelled = true;
      clearTimeout(timer);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, deps);
}
