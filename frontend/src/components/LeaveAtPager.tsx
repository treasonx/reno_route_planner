import { bestOf, formatDay, verdictClass, verdictGlyph } from "../lib/verdict";
import type { HourOut } from "../types";

interface Props {
  hours: readonly HourOut[];
  index: number;
  pageSize: number;
  onSelect: (index: number) => void;
}

export function LeaveAtPager({ hours, index, pageSize, onSelect }: Props) {
  const pages = Math.max(1, Math.ceil(hours.length / pageSize));
  const page = Math.min(Math.floor(index / pageSize), pages - 1);
  const start = page * pageSize;
  const visible = hours.slice(start, start + pageSize);
  const selected = hours[index];
  const goPage = (p: number) => {
    if (p >= 0 && p < pages) onSelect(p * pageSize);
  };

  return (
    <section class="pager" aria-label="Departure time">
      <div class="pager-head">
        <h2 class="eyebrow">Leave at</h2>
        {selected && (
          <span class="pager-selected">
            {formatDay(selected.depart)} {selected.label === "Now" ? "now" : selected.label} PT
          </span>
        )}
      </div>
      <div class="pager-row">
        <button type="button" class="arrow" aria-label="Earlier hours" disabled={page === 0} onClick={() => goPage(page - 1)}>
          <svg width="20" height="20" viewBox="0 0 24 24" aria-hidden="true" class="icon"><path d="M15 18l-6-6 6-6" /></svg>
        </button>
        <div class={`hours cols-${pageSize}`} role="listbox" aria-label="Departure hour">
          {visible.map((h, i) => {
            const idx = start + i;
            const isSel = idx === index;
            const prev = hours[idx - 1];
            const newDay = idx === 0 || (prev !== undefined && formatDay(prev.depart) !== formatDay(h.depart));
            return (
              <button
                key={h.depart}
                type="button"
                role="option"
                aria-selected={isSel}
                class={`hour ${verdictClass(h.best.verdict)}${isSel ? " selected" : ""}`}
                aria-label={`Leave ${formatDay(h.depart)} ${h.label}: best route ${h.best.verdict}`}
                onClick={() => onSelect(idx)}
              >
                <span class="hour-label num">{h.label}</span>
                <span class="hour-sub">
                  {newDay && i === 0
                    ? `${formatDay(h.depart)} ${verdictGlyph(h.best.verdict)}`
                    : `${verdictGlyph(h.best.verdict)} ${h.best.verdict}`}
                </span>
              </button>
            );
          })}
        </div>
        <button type="button" class="arrow" aria-label="Later hours" disabled={page >= pages - 1} onClick={() => goPage(page + 1)}>
          <svg width="20" height="20" viewBox="0 0 24 24" aria-hidden="true" class="icon"><path d="M9 18l6-6-6-6" /></svg>
        </button>
      </div>
      <div class="chunks" aria-hidden="true">
        {Array.from({ length: pages }, (_, p) => {
          const lvl = bestOf(hours.slice(p * pageSize, p * pageSize + pageSize).map((h) => h.best.verdict));
          return <span key={p} class={`chunk ${verdictClass(lvl)}${p === page ? " current" : ""}`} />;
        })}
      </div>
    </section>
  );
}
