import { useId } from "preact/hooks";
import { verdictClass, verdictGlyph } from "../lib/verdict";
import type { DayOut, RouteKey } from "../types";

interface Props {
  days: readonly DayOut[];
  selected: string | null;
  /** Verdicts follow this highway; ★ marks days where it's the best highway. */
  route: RouteKey;
  routeName: string;
  onSelect: (date: string | null) => void;
}

export function TenDay({ days, selected, route, routeName, onSelect }: Props) {
  const today = days[0]?.date ?? null;
  const headingId = useId();
  return (
    <section class="card" aria-labelledby={headingId}>
      <div class="card-head">
        <h2 id={headingId}>10-day outlook · {routeName}</h2>
        <span class="muted">★ best that day · tap to plan</span>
      </div>
      <div class="days" role="radiogroup" aria-labelledby={headingId}>
        {days.map((d) => {
          const isSel = (selected ?? today) === d.date;
          const v = d.routes[route];
          const best = d.best_route === route && d.verdict !== "NO GO";
          const reasons = d.best_route === route ? d.reasons : [];
          return (
            <button
              key={d.date}
              type="button"
              role="radio"
              class={`day ${verdictClass(v)}${isSel ? " selected" : ""}${d.low_confidence ? " low" : ""}`}
              aria-checked={isSel}
              aria-label={`${d.dow} ${d.day}: ${routeName} ${v}${best ? ", best highway" : ""}${
                d.low_confidence ? ", low confidence" : ""
              }${reasons.length ? `. ${reasons.join(". ")}` : ""}`}
              title={reasons.join(". ") || undefined}
              onClick={() => onSelect(d.date === today ? null : d.date)}
            >
              <span class="day-dow">{d.dow}</span>
              <span class="day-num num">{d.day}</span>
              <span class="day-verdict">
                {best ? "★" : ""}
                {verdictGlyph(v)}
                {d.low_confidence ? "?" : ""}
              </span>
            </button>
          );
        })}
      </div>
    </section>
  );
}
