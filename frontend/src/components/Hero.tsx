import { verdictClass, verdictGlyph } from "../lib/verdict";
import type { HourOut, PlanResponse, RouteKey } from "../types";

interface Props {
  plan: PlanResponse;
  hour: HourOut;
  route: RouteKey;
  recommended: boolean;
  stale: boolean;
}

/** The verdict for the selected highway at the selected departure. */
export function Hero({ plan, hour, route, recommended, stale }: Props) {
  const r = hour.routes[route];
  const name = plan.corridors[route].name;
  const v = r.verdict;
  const leaving = hour.label === "Now" ? "now" : hour.label;
  const sub =
    v === "GO"
      ? r.go_until
        ? `GO for departures until ${r.go_until}`
        : "GO"
      : v === "CAUTION"
        ? `Drive with care on ${name}`
        : `Don’t cross on ${name}`;
  return (
    <section class={`hero ${verdictClass(v)}${stale ? " is-stale" : ""}`} aria-live="polite">
      <p class="eyebrow hero-kicker">
        {name} · leaving {leaving}
        {recommended ? " · ★ recommended" : ""}
      </p>
      <h2 class="hero-title" key={`${hour.depart}|${route}`}>
        {v}
      </h2>
      <p class="hero-sub">
        <span aria-hidden="true">{verdictGlyph(v)} </span>
        {sub}
      </p>
      <p class="hero-body">{r.caption}</p>
    </section>
  );
}
