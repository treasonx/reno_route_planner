import { useState } from "preact/hooks";

import { Header } from "./components/Header";
import { Hero } from "./components/Hero";
import { LeaveAtPager } from "./components/LeaveAtPager";
import { RoutesCard } from "./components/RoutesCard";
import { DataUnavailable, Footer, Skeleton, StaleBanner } from "./components/Status";
import { TenDay } from "./components/TenDay";
import { useMediaQuery } from "./hooks/useMediaQuery";
import { isStale, usePlan } from "./hooks/usePlan";
import { loadDirection, saveDirection } from "./lib/storage";
import type { Direction, PlanResponse, RouteKey } from "./types";

const DESKTOP = "(min-width: 900px)";

interface Selection {
  key: string;
  hour: number;
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
  const [selection, setSelection] = useState<Selection>({ key: "", hour: 0, tab: null });
  const desktop = useMediaQuery(DESKTOP);
  const { state, reload } = usePlan(direction, date);

  const plan = state.status === "ready" ? state.plan : state.status === "error" ? state.lastPlan : undefined;
  const planKey = plan ? `${plan.direction}|${plan.hours[0]?.depart ?? ""}` : "";

  // Selection is keyed to the loaded window: a new day / direction opens at the right hour
  // and follows the recommendation, while a 5-minute refresh of the same window keeps it.
  // (Derived during render, not in an effect, so it can never race a user's click.)
  const current: Selection =
    selection.key === planKey
      ? selection
      : { key: planKey, hour: plan ? initialHourIndex(plan, date) : 0, tab: null };
  const hourIndex = current.hour;
  const routeTab = current.tab;
  const setRouteTab = (tab: RouteKey) => setSelection({ ...current, tab });

  const swap = () => {
    const next: Direction = direction === "reno-sac" ? "sac-reno" : "reno-sac";
    saveDirection(next);
    setDirection(next);
  };

  // Tabs follow the recommendation for the newly selected hour.
  const selectHour = (i: number) => setSelection({ key: planKey, hour: i, tab: null });

  if (!plan) {
    return (
      <main class="app">
        <Header direction={direction} onSwap={swap} />
        {state.status === "error" ? <DataUnavailable message={state.error} onRetry={() => void reload()} /> : <Skeleton />}
        <Footer notes={[]} />
      </main>
    );
  }

  const hour = plan.hours[Math.min(hourIndex, plan.hours.length - 1)];
  if (!hour) {
    return (
      <main class="app">
        <Header direction={direction} onSwap={swap} />
        <DataUnavailable message="No departures in this window" onRetry={() => void reload()} />
      </main>
    );
  }
  const stale = isStale(plan) || state.status === "error";
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
