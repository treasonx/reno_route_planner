import { useId } from "preact/hooks";

import { verdictClass, verdictGlyph } from "../lib/verdict";
import { type HourOut, type PlanResponse, ROUTE_KEYS, type RouteKey } from "../types";

interface Props {
  plan: PlanResponse;
  hour: HourOut;
  selected: RouteKey;
  recommended: RouteKey | null;
  onSelect: (route: RouteKey) => void;
}

/** One card per highway: name, its verdict for the selected departure, and ★ BEST. */
export function HighwaySelector({ plan, hour, selected, recommended, onSelect }: Props) {
  const labelId = useId();
  const idx = ROUTE_KEYS.indexOf(selected);

  // Radio-group keyboard pattern: arrows move (and select) within the group, no wrap.
  const onKey = (e: KeyboardEvent) => {
    const last = ROUTE_KEYS.length - 1;
    let target: number;
    if (e.key === "ArrowRight" || e.key === "ArrowDown") target = Math.min(last, idx + 1);
    else if (e.key === "ArrowLeft" || e.key === "ArrowUp") target = Math.max(0, idx - 1);
    else if (e.key === "Home") target = 0;
    else if (e.key === "End") target = last;
    else return;
    e.preventDefault();
    const next = ROUTE_KEYS[target];
    if (next) {
      if (next !== selected) onSelect(next);
      document.getElementById(`${labelId}-${next}`)?.focus();
    }
  };

  return (
    <section class="highway" aria-labelledby={labelId}>
      <h2 class="eyebrow" id={labelId}>
        Highway
      </h2>
      <div class="highways" role="radiogroup" aria-labelledby={labelId} onKeyDown={onKey}>
        {ROUTE_KEYS.map((k) => {
          const v = hour.routes[k].verdict;
          const on = k === selected;
          const best = k === recommended;
          return (
            <button
              key={k}
              id={`${labelId}-${k}`}
              type="button"
              role="radio"
              aria-checked={on}
              tabIndex={on ? 0 : -1}
              aria-label={`${plan.corridors[k].name}: ${v}${best ? ", recommended" : ""}`}
              class={`highway-card${on ? " selected" : ""}`}
              onClick={() => onSelect(k)}
            >
              {best && (
                <span class="best-badge" aria-hidden="true">
                  ★ BEST
                </span>
              )}
              <span class="highway-name">{plan.corridors[k].name}</span>
              <span class={`highway-status ${verdictClass(v)}`}>
                {verdictGlyph(v)} {v}
              </span>
            </button>
          );
        })}
      </div>
    </section>
  );
}
