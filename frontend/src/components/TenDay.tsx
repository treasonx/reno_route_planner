import { verdictClass, verdictGlyph } from "../lib/verdict";
import type { DayOut } from "../types";

interface Props {
  days: readonly DayOut[];
  selected: string | null;
  onSelect: (date: string | null) => void;
}

export function TenDay({ days, selected, onSelect }: Props) {
  const today = days[0]?.date ?? null;
  return (
    <section class="card" aria-label="Next 10 days">
      <div class="card-head">
        <h2>Next 10 days</h2>
        <span class="muted">Tap a day to plan it</span>
      </div>
      <div class="days">
        {days.map((d) => {
          const isSel = (selected ?? today) === d.date;
          return (
            <button
              key={d.date}
              type="button"
              class={`day ${verdictClass(d.verdict)}${isSel ? " selected" : ""}${d.low_confidence ? " low" : ""}`}
              aria-pressed={isSel}
              aria-label={`${d.dow} ${d.day}: ${d.verdict}${d.low_confidence ? ", low confidence" : ""}${
                d.reasons.length ? `. ${d.reasons.join(". ")}` : ""
              }`}
              title={d.reasons.join(". ") || undefined}
              onClick={() => onSelect(d.date === today ? null : d.date)}
            >
              <span class="day-dow">{d.dow}</span>
              <span class="day-num num">{d.day}</span>
              <span class="day-verdict">
                {verdictGlyph(d.verdict)}
                {d.low_confidence ? "?" : ""}
              </span>
            </button>
          );
        })}
      </div>
    </section>
  );
}
