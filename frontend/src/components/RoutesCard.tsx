import { useSwipe } from "../hooks/useSwipe";
import { formatTime, verdictClass, verdictGlyph } from "../lib/verdict";
import { type HourOut, type PlanResponse, ROUTE_KEYS, type RouteKey } from "../types";
import { RouteProfile } from "./RouteProfile";

interface Props {
  plan: PlanResponse;
  hour: HourOut;
  selected: RouteKey;
  onSelect: (r: RouteKey) => void;
  desktop: boolean;
}

function Legend() {
  return (
    <ul class="legend" aria-label="Legend">
      <li><span class="swatch go" />Go</li>
      <li><span class="swatch caution" />Caution</li>
      <li><span class="swatch nogo" />No go</li>
    </ul>
  );
}

function Detail({ plan, hour, route }: { plan: PlanResponse; hour: HourOut; route: RouteKey }) {
  const r = hour.routes[route];
  const c = plan.corridors[route];
  return (
    <>
      <RouteProfile corridor={c} route={r} />
      <div class="caption">
        <p>{r.caption}</p>
        <p class="muted">
          Leave {hour.label === "Now" ? "now" : hour.label} → {c.summit} around {formatTime(r.summit_eta)}
        </p>
      </div>
    </>
  );
}

export function RoutesCard({ plan, hour, selected, onSelect, desktop }: Props) {
  const idx = ROUTE_KEYS.indexOf(selected);
  const swipe = useSwipe((dir) => {
    const next = ROUTE_KEYS[dir === "next" ? Math.min(ROUTE_KEYS.length - 1, idx + 1) : Math.max(0, idx - 1)];
    if (next) onSelect(next);
  });
  const leaving = hour.label === "Now" ? "now" : hour.label;

  if (desktop) {
    return (
      <section class="card routes" aria-label="All routes">
        <div class="card-head">
          <h2>All routes</h2>
          <span class="muted">Leaving {leaving} · colored by when you reach each stretch</span>
        </div>
        {ROUTE_KEYS.map((k) => {
          const r = hour.routes[k];
          const isBest = k === hour.best.route && hour.best.verdict !== "NO GO";
          return (
            <article key={k} class={`route-row${isBest ? " best" : ""}`}>
              <div class="route-info">
                <div class="route-title">
                  <h3>{plan.corridors[k].name}</h3>
                  <span class={`pill ${verdictClass(r.verdict)}`}>
                    {verdictGlyph(r.verdict)} {r.verdict}
                  </span>
                </div>
                {isBest && <p class="best-tag">Best route</p>}
                <p>{r.caption}</p>
                <p class="muted">
                  Leave {leaving} → {plan.corridors[k].summit} around {formatTime(r.summit_eta)}
                </p>
              </div>
              <div class="route-graphic">
                <RouteProfile corridor={plan.corridors[k]} route={r} />
              </div>
            </article>
          );
        })}
        <Legend />
      </section>
    );
  }

  const onKey = (e: KeyboardEvent) => {
    if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
    e.preventDefault();
    const n = ROUTE_KEYS[(idx + (e.key === "ArrowRight" ? 1 : ROUTE_KEYS.length - 1)) % ROUTE_KEYS.length];
    if (n) {
      onSelect(n);
      document.getElementById(`tab-${n}`)?.focus();
    }
  };

  return (
    <section class="card routes" aria-label="All routes">
      <div class="card-head">
        <h2>All routes</h2>
        <span class="muted">Leaving {leaving}</span>
      </div>
      <div class="tabs" role="tablist" aria-label="Route" onKeyDown={onKey}>
        {ROUTE_KEYS.map((k) => {
          const v = hour.routes[k].verdict;
          const sel = k === selected;
          return (
            <button
              key={k}
              id={`tab-${k}`}
              type="button"
              role="tab"
              aria-selected={sel}
              aria-controls="route-panel"
              tabIndex={sel ? 0 : -1}
              class={`tab${sel ? " selected" : ""}`}
              onClick={() => onSelect(k)}
            >
              <span class="tab-name">{plan.corridors[k].name}</span>
              <span class={`tab-status ${verdictClass(v)}`}>
                {verdictGlyph(v)} {v}
              </span>
            </button>
          );
        })}
      </div>
      <div id="route-panel" role="tabpanel" class="swipe-area" {...swipe}>
        <Detail plan={plan} hour={hour} route={selected} />
      </div>
      <div class="card-foot">
        <Legend />
        <div class="dots" aria-hidden="true">
          {ROUTE_KEYS.map((k) => (
            <span key={k} class={`dot${k === selected ? " on" : ""}`} />
          ))}
        </div>
      </div>
    </section>
  );
}
