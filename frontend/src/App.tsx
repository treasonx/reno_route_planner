import { useState } from "preact/hooks";

import { Header } from "./components/Header";
import { Hero } from "./components/Hero";
import { LeaveAtPager } from "./components/LeaveAtPager";
import { RoutesCard } from "./components/RoutesCard";
import { DataUnavailable, Footer, Skeleton, StaleBanner } from "./components/Status";
import { TenDay } from "./components/TenDay";
import { useMediaQuery } from "./hooks/useMediaQuery";
import { usePlan } from "./hooks/usePlan";
import { loadDirection, saveDirection } from "./lib/storage";
import type { Direction, PlanResponse, RouteKey } from "./types";

const DESKTOP = "(min-width: 900px)";

/**
 * The user's pick, tied to the (direction, date) it was made in. The departure is stored by
 * timestamp, not index, so an hourly refresh that shifts ``hours`` keeps the same departure.
 */
interface Selection {
  ctx: string;
  depart: string | null;
  tab: RouteKey | null;
}

/** Index of the 6 AM departure when a future day is opened, else 0. */
export const initialHourIndex = (plan: PlanResponse, date: string | null): number => {
  if (date === null) return 0;
  const six = plan.hours.findIndex((h) => h.label === "6 AM");
  return six >= 0 ? six : 0;
};

export function App() {
  const [direction, setDirection] = useState<Direction>(loadDirection);
  const [date, setDate] = useState<string | null>(null);
  const [selection, setSelection] = useState<Selection>({ ctx: "", depart: null, tab: null });
  const desktop = useMediaQuery(DESKTOP);
  const { state, reload } = usePlan(direction, date);

  const plan = state.status === "ready" ? state.plan : state.status === "error" ? state.lastPlan : undefined;
  const ctx = `${direction}|${date ?? ""}`;

  // Derived during render (not in an effect) so it can never race a user's click:
  // - same (direction, date) and the picked departure is still in the plan -> keep it and its tab;
  // - otherwise (new day / direction, or the departure rolled off) -> default hour, tab follows
  //   the recommendation.
  const kept = plan && selection.ctx === ctx && selection.depart !== null
    ? plan.hours.findIndex((h) => h.depart === selection.depart)
    : -1;
  const hourIndex = kept >= 0 ? kept : plan ? initialHourIndex(plan, date) : 0;
  const routeTab = kept >= 0 ? selection.tab : null;

  const swap = () => {
    const next: Direction = direction === "reno-sac" ? "sac-reno" : "reno-sac";
    saveDirection(next);
    setDirection(next);
  };

  // Tabs follow the recommendation for the newly selected hour.
  const selectHour = (i: number) => setSelection({ ctx, depart: plan?.hours[i]?.depart ?? null, tab: null });

  if (!plan) {
    return (
      <main class="app">
        <Header direction={direction} onSwap={swap} />
        {state.status === "error" ? <DataUnavailable message={state.error} onRetry={() => void reload()} /> : <Skeleton />}
        <Footer notes={[]} />
      </main>
    );
  }

  const hour = plan.hours[hourIndex];
  // The API schema doesn't guarantee a non-empty window, so keep a safe fallback (never a verdict).
  if (!hour) {
    return (
      <main class="app">
        <Header direction={direction} onSwap={swap} />
        <DataUnavailable message="No departures in this window" onRetry={() => void reload()} />
        <Footer notes={plan.notes} />
      </main>
    );
  }
  const setRouteTab = (tab: RouteKey) => setSelection({ ctx, depart: hour.depart, tab });
  // One definition of stale: the server's flag, plus "our last refresh failed".
  const stale = plan.stale || state.status === "error";
  const selectedRoute = routeTab ?? hour.best.route;

  return (
    <main class={`app${desktop ? " desktop" : ""}`}>
      <Header direction={direction} onSwap={swap} />
      {stale && <StaleBanner plan={plan} error={state.status === "error" ? state.error : null} />}
      <LeaveAtPager hours={plan.hours} index={hourIndex} pageSize={desktop ? 6 : 3} onSelect={selectHour} />
      <div class="columns">
        <div class="col-main">
          <Hero hour={hour} stale={stale} />
          {desktop && <TenDay days={plan.days} selected={date} onSelect={setDate} />}
        </div>
        <div class="col-side">
          <RoutesCard plan={plan} hour={hour} selected={selectedRoute} onSelect={setRouteTab} desktop={desktop} />
          {!desktop && <TenDay days={plan.days} selected={date} onSelect={setDate} />}
        </div>
      </div>
      <Footer notes={plan.notes} />
    </main>
  );
}
