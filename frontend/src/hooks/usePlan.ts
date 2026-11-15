import { useCallback, useEffect, useRef, useState } from "preact/hooks";

import { ApiError, fetchPlan } from "../api";
import type { Direction, PlanResponse } from "../types";
import { usePolling } from "./usePolling";

export type PlanState =
  | { status: "loading" }
  | { status: "ready"; plan: PlanResponse }
  | { status: "error"; error: string; lastPlan?: PlanResponse }
  /** The server is up but has no data yet (fresh start): retried every WARMUP_RETRY_MS. */
  | { status: "warming" };

export const POLL_MS = 5 * 60 * 1000;
export const WARMUP_RETRY_MS = 5_000;

const LOADING: PlanState = { status: "loading" };

/**
 * Fetches the plan for (direction, date); keeps the last good plan when a poll fails.
 *
 * State is tagged with the ``direction|date`` it was fetched for. A tag that doesn't match
 * the current arguments reads as loading *during render*, so a new direction or day can
 * never be painted with the previous selection's verdicts (not even for one frame).
 */
export function usePlan(direction: Direction, date: string | null) {
  const key = `${direction}|${date ?? ""}`;
  const [stored, setStored] = useState<{ key: string; state: PlanState }>({ key, state: LOADING });
  const controller = useRef<AbortController | null>(null);
  const lastGood = useRef<{ key: string; plan: PlanResponse } | null>(null);

  const load = useCallback(async () => {
    controller.current?.abort();
    const ac = new AbortController();
    controller.current = ac;
    try {
      const plan = await fetchPlan(direction, date, ac.signal);
      if (ac.signal.aborted) return;
      lastGood.current = { key, plan };
      setStored({ key, state: { status: "ready", plan } });
    } catch (err) {
      if (ac.signal.aborted) return;
      const error = err instanceof Error ? err.message : "Network error";
      const lastPlan = lastGood.current?.key === key ? lastGood.current.plan : undefined;
      if (!lastPlan && err instanceof ApiError && err.status === 503) {
        setStored({ key, state: { status: "warming" } });
        return;
      }
      setStored({ key, state: lastPlan ? { status: "error", error, lastPlan } : { status: "error", error } });
    }
  }, [direction, date, key]);

  // Abort the in-flight request when the selection changes or the component unmounts.
  useEffect(() => () => controller.current?.abort(), [key]);

  usePolling(load, POLL_MS, [load]);
  const state = stored.key === key ? stored.state : LOADING;

  // While the server is warming up, retry quickly instead of waiting for the 5-minute poll.
  useEffect(() => {
    if (state.status !== "warming") return;
    const t = setTimeout(() => void load(), WARMUP_RETRY_MS);
    return () => clearTimeout(t);
  }, [state, load]);
  return { state, reload: load };
}
