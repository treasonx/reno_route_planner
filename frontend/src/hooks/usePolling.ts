import { useEffect, useRef } from "preact/hooks";

/**
 * Calls ``fn`` now and then every ``intervalMs`` using chained timeouts. Pauses while the
 * page is hidden and refreshes immediately on return if the data is older than the interval.
 */
export function usePolling(fn: () => Promise<void>, intervalMs: number, deps: readonly unknown[]) {
  const last = useRef(0);

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | undefined;
    let cancelled = false;

    const tick = async () => {
      if (cancelled) return;
      last.current = Date.now();
      await fn();
      if (!cancelled && document.visibilityState === "visible") {
        timer = setTimeout(() => void tick(), intervalMs);
      }
    };

    const onVisibility = () => {
      clearTimeout(timer);
      if (document.visibilityState !== "visible") return;
      const age = Date.now() - last.current;
      if (age >= intervalMs) void tick();
      else timer = setTimeout(() => void tick(), intervalMs - age);
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
