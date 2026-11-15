import { useCallback, useEffect, useRef, useState } from "preact/hooks";

import { fetchPlan } from "../api";
import type { Direction, PlanResponse } from "../types";
import { usePolling } from "./usePolling";

export type PlanState =
  | { status: "loading" }
  | { status: "ready"; plan: PlanResponse }
  | { status: "error"; error: string; lastPlan?: PlanResponse };

export const POLL_MS = 5 * 60 * 1000;
const STALE_MS = 15 * 60 * 1000;

/** Fetches the plan for (direction, date); keeps the last good plan when a poll fails. */
export function usePlan(direction: Direction, date: string | null) {
  const [state, setState] = useState<PlanState>({ status: "loading" });
  const controller = useRef<AbortController | null>(null);
  const lastGood = useRef<PlanResponse | undefined>(undefined);

  const load = useCallback(async () => {
    controller.current?.abort();
    const ac = new AbortController();
    controller.current = ac;
    try {
      const plan = await fetchPlan(direction, date, ac.signal);
      if (ac.signal.aborted) return;
      lastGood.current = plan;
      setState({ status: "ready", plan });
    } catch (err) {
      if (ac.signal.aborted) return;
      const error = err instanceof Error ? err.message : "Network error";
      const lastPlan = lastGood.current;
      setState(lastPlan ? { status: "error", error, lastPlan } : { status: "error", error });
    }
  }, [direction, date]);

  // A new (direction, date) must never show the previous selection's plan.
  useEffect(() => {
    lastGood.current = undefined;
    setState({ status: "loading" });
    return () => controller.current?.abort();
  }, [direction, date]);

  usePolling(load, POLL_MS, [load]);
  return { state, reload: load };
}

export const isStale = (plan: PlanResponse, now: number = Date.now()): boolean =>
  plan.stale || now - new Date(plan.generated_at).getTime() > STALE_MS;
