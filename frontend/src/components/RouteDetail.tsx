import { useSwipe } from "../hooks/useSwipe";
import { formatTime } from "../lib/verdict";
import { type HourOut, type PlanResponse, ROUTE_KEYS, type RouteKey } from "../types";
import { RouteProfile } from "./RouteProfile";

interface Props {
  plan: PlanResponse;
  hour: HourOut;
  route: RouteKey;
  onSelect: (route: RouteKey) => void;
  desktop: boolean;
}

/** Profile of the selected highway. Swiping it changes highway (same as the selector). */
export function RouteDetail({ plan, hour, route, onSelect, desktop }: Props) {
  const idx = ROUTE_KEYS.indexOf(route);
  const swipe = useSwipe((dir) => {
    const next = ROUTE_KEYS[dir === "next" ? Math.min(ROUTE_KEYS.length - 1, idx + 1) : Math.max(0, idx - 1)];
    if (next && next !== route) onSelect(next);
  });
  const r = hour.routes[route];
  const c = plan.corridors[route];
  const leaving = hour.label === "Now" ? "now" : hour.label;

  return (
    <section class="card route-detail" aria-label={`Along ${c.name}`}>
      <div class="card-head">
        <h2 class="route-detail-title">Along {c.name}</h2>
        <span class="muted">{desktop ? "Colored by when you reach each stretch" : "Swipe to change highway"}</span>
      </div>
      <div class="swipe-area" {...swipe}>
        <RouteProfile corridor={c} route={r} />
      </div>
      <div class="caption">
        <p>{r.caption}</p>
        <p class="muted">
          Leave {leaving} → {c.summit} around {formatTime(r.summit_eta)}
        </p>
      </div>
      <div class="card-foot">
        <ul class="legend" aria-label="Legend">
          <li><span class="swatch go" />Go</li>
          <li><span class="swatch caution" />Caution</li>
          <li><span class="swatch nogo" />No go</li>
        </ul>
        {!desktop && (
          <div class="dots" aria-hidden="true">
            {ROUTE_KEYS.map((k) => (
              <span key={k} class={`dot${k === route ? " on" : ""}`} />
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
