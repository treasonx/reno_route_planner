import { useState } from "preact/hooks";

import { Header } from "./components/Header";
import { Hero } from "./components/Hero";
import { HighwaySelector } from "./components/HighwaySelector";
import { LeaveAtPager } from "./components/LeaveAtPager";
import { RecommendationBanner } from "./components/RecommendationBanner";
import { RouteDetail } from "./components/RouteDetail";
import { DataUnavailable, Footer, Skeleton, StaleBanner, StartingUp } from "./components/Status";
import { TenDay } from "./components/TenDay";
import { useMediaQuery } from "./hooks/useMediaQuery";
import { usePlan } from "./hooks/usePlan";
import { loadDirection, saveDirection } from "./lib/storage";
import type { Direction, PlanResponse, RouteKey } from "./types";

const DESKTOP = "(min-width: 900px)";

/**
 * The picked departure, tied to the (direction, date) it was made in. It's stored by timestamp,
 * not index, so an hourly refresh that shifts ``hours`` keeps the same departure.
 */
interface Selection {
  ctx: string;
  depart: string | null;
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
  const [selection, setSelection] = useState<Selection>({ ctx: "", depart: null });
  // The highway the user picked. null = follow the recommendation ("Auto"). It's independent of
  // the departure: changing the time keeps the highway, changing the highway keeps the time.
  // Never persisted, so every load starts on the recommended highway.
  const [pinned, setPinned] = useState<RouteKey | null>(null);
  const desktop = useMediaQuery(DESKTOP);
  const { state, reload } = usePlan(direction, date);

  const plan = state.status === "ready" ? state.plan : state.status === "error" ? state.lastPlan : undefined;
  const ctx = `${direction}|${date ?? ""}`;

  // Derived during render (not in an effect) so it can never race a user's click:
  // - same (direction, date) and the picked departure is still in the plan -> keep it;
  // - otherwise (new day / direction, or the departure rolled off) -> default hour.
  const kept = plan && selection.ctx === ctx && selection.depart !== null
    ? plan.hours.findIndex((h) => h.depart === selection.depart)
    : -1;
  const hourIndex = kept >= 0 ? kept : plan ? initialHourIndex(plan, date) : 0;

  const swap = () => {
    const next: Direction = direction === "reno-sac" ? "sac-reno" : "reno-sac";
    saveDirection(next);
    setDirection(next);
  };

  const selectHour = (i: number) => setSelection({ ctx, depart: plan?.hours[i]?.depart ?? null });

  if (!plan) {
    return (
      <main class="app">
        <Header direction={direction} onSwap={swap} />
        {state.status === "error" ? (
          <DataUnavailable message={state.error} onRetry={() => void reload()} />
        ) : state.status === "warming" ? (
          <StartingUp />
        ) : (
          <Skeleton />
        )}
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
  // Picking a highway pins the departure too, so it can't drift on the next refresh.
  const pickRoute = (route: RouteKey) => {
    setSelection({ ctx, depart: hour.depart });
    setPinned(route);
  };
  // One definition of stale: the server's flag, plus "our last refresh failed".
  const stale = plan.stale || state.status === "error";
  // Nothing is "recommended" when every highway is NO GO.
  const recommended = hour.best.verdict === "NO GO" ? null : hour.best.route;
  const route = pinned ?? hour.best.route;
  const routeName = plan.corridors[route].name;

  return (
    <main class={`app${desktop ? " desktop" : ""}`}>
      <Header direction={direction} onSwap={swap} />
      {stale && <StaleBanner plan={plan} error={state.status === "error" ? state.error : null} />}
      <div class="selector-row">
        <HighwaySelector plan={plan} hour={hour} selected={route} recommended={recommended} onSelect={pickRoute} />
        <RecommendationBanner
          plan={plan}
          hour={hour}
          selected={route}
          recommended={recommended}
          pinned={pinned !== null}
          onUse={pickRoute}
          onAuto={() => setPinned(null)}
        />
      </div>
      <LeaveAtPager
        hours={plan.hours}
        index={hourIndex}
        pageSize={desktop ? 6 : 3}
        route={route}
        routeName={routeName}
        onSelect={selectHour}
      />
      <div class="columns">
        <div class="col-main">
          <Hero plan={plan} hour={hour} route={route} recommended={route === recommended} stale={stale} />
          {desktop && (
            <TenDay days={plan.days} selected={date} route={route} routeName={routeName} onSelect={setDate} />
          )}
        </div>
        <div class="col-side">
          <RouteDetail plan={plan} hour={hour} route={route} onSelect={pickRoute} desktop={desktop} />
          {!desktop && (
            <TenDay days={plan.days} selected={date} route={route} routeName={routeName} onSelect={setDate} />
          )}
        </div>
      </div>
      <Footer notes={plan.notes} />
    </main>
  );
}
