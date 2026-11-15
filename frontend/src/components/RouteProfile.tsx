import { verdictClass } from "../lib/verdict";
import type { CorridorOut, RouteOut } from "../types";

const BASE_Y = 140;

/** Side-on elevation profile; each segment is colored AND dashed by its verdict. */
export function RouteProfile({ corridor, route }: { corridor: CorridorOut; route: RouteOut }) {
  const stops = corridor.stops;
  const first = stops[0];
  const last = stops[stops.length - 1];
  const area =
    stops.map((s) => `${s.x},${s.y}`).join(" ") + (first && last ? ` ${last.x},${BASE_Y} ${first.x},${BASE_Y}` : "");
  const peaks = stops.filter((s) => s.peak_label);

  return (
    <figure class="profile">
      <svg
        viewBox="0 0 358 150"
        role="img"
        aria-label={`${corridor.name} elevation profile: ${route.verdict}. ${route.caption}`}
      >
        <polygon points={area} class="profile-ground" />
        <line x1="10" y1={BASE_Y} x2="348" y2={BASE_Y} class="profile-base" />
        {stops.slice(1).map((b, i) => {
          const a = stops[i];
          const lvl = route.segments[i];
          if (!a || !lvl) return null;
          return (
            <line key={b.id} x1={a.x} y1={a.y} x2={b.x} y2={b.y} class={`seg seg-${verdictClass(lvl)}`}>
              <title>{`${a.name} → ${b.name}: ${lvl}`}</title>
            </line>
          );
        })}
        {peaks.map((p, i) => (
          <g key={p.id}>
            <circle cx={p.x} cy={p.y} r="3.5" class="peak" />
            <text
              x={peaks.length > 1 ? (i === 0 ? p.x - 6 : p.x + 6) : p.x}
              y={Math.max(10, p.y - 9)}
              text-anchor={peaks.length > 1 ? (i === 0 ? "end" : "start") : "middle"}
              class="peak-label"
            >
              {p.peak_label}
            </text>
          </g>
        ))}
      </svg>
      <figcaption class="towns">
        {corridor.towns.map((t) => (
          <span key={t}>{t}</span>
        ))}
      </figcaption>
    </figure>
  );
}
