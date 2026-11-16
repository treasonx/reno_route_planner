import {
  STAGGER_FROM,
  type StopRow,
  anySnow,
  barPx,
  buildStopRows,
  elevationDomain,
  fmtInches,
  fmtRate,
  fmtTemp,
  formatClock,
  freezeLinePct,
  profilePoints,
  stopLabel,
  summarizeRouteWeather,
  tempTone,
} from "../lib/weather";
import type { CorridorOut, RouteOut } from "../types";

interface Props {
  corridor: CorridorOut;
  route: RouteOut;
  depart: string;
  leaving: string;
  stale: boolean;
}

const DEPTH_CAP_IN = 36;
const DEPTH_MAX_PX = 30;
const RATE_CAP_IN = 1;
const RATE_MAX_PX = 16;

/** Column count for the per-stop grids (a CSS custom property, so it is passed as a string). */
const columns = (n: number): string => `--n:${n}`;

function Thermometer() {
  return (
    <svg width="10" height="12" viewBox="0 0 10 12" class="wx-glyph">
      <rect x="3.5" y="0.5" width="3" height="7.5" rx="1.5" fill="none" stroke="currentColor" />
      <circle cx="5" cy="9.3" r="2.2" fill="currentColor" />
    </svg>
  );
}

function Flake() {
  return (
    <svg width="12" height="12" viewBox="0 0 12 12" class="wx-glyph">
      <path d="M6 1v10M1.7 3.5l8.6 5M1.7 8.5l8.6-5" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" />
    </svg>
  );
}

/** Evenly spaced elevation profile (one column per stop) with the summit freezing level. */
function WeatherProfile({ rows, freezingFt }: { rows: StopRow[]; freezingFt: number | null }) {
  const domain = elevationDomain(rows.map((r) => r.elevationFt));
  const pts = profilePoints(rows.map((r) => r.elevationFt), domain);
  const first = pts[0];
  const last = pts[pts.length - 1];
  const line = pts.map((p, i) => `${i ? "L" : "M"}${p.x} ${p.y}`).join(" ");
  const area = first && last ? `${line} L${last.x} 100 L${first.x} 100 Z` : "";
  const freeze = freezeLinePct(freezingFt, domain);
  return (
    <div class="wx-profile">
      <svg viewBox="0 0 100 100" preserveAspectRatio="none">
        <path d={area} class="wx-ground" />
        <path d={line} class="wx-line" vector-effect="non-scaling-stroke" />
      </svg>
      {freeze !== null && freezingFt !== null && (
        <div class="wx-freeze" style={{ top: `${freeze}%` }}>
          <span>32°F at {freezingFt.toLocaleString("en-US")}′</span>
        </div>
      )}
      {pts.map((p, i) => (
        <span
          key={rows[i]?.id ?? i}
          class={`wx-dot${rows[i]?.isSummit ? " summit" : ""}`}
          style={{ left: `${p.x}%`, top: `${p.y}%` }}
        />
      ))}
    </div>
  );
}

/** Temperature and snow at each stop of the selected highway, for when you pass it. */
export function RouteWeather({ corridor, route, depart, leaving, stale }: Props) {
  const rows = buildStopRows(corridor, route, depart);
  const n = rows.length;
  const snowy = anySnow(rows);

  return (
    <section class={`card route-weather${stale ? " is-stale" : ""}`} aria-label={`Weather on ${corridor.name}`}>
      <div class="card-head">
        <h2 class="route-detail-title">Weather on {corridor.name}</h2>
        <span class="muted">Leaving {leaving} · as you pass</span>
      </div>

      <div class="wx" aria-hidden="true">
        <p class="wx-lane wx-lane-temp">
          <Thermometer />
          Air temp <span class="wx-unit">°F</span>
        </p>
        <div class="wx-cols" style={columns(n)}>
          {rows.map((r) => (
            <div key={r.id} class={`wx-col${r.isSummit ? " summit" : ""}`}>
              <span class={`wx-temp num ${tempTone(r.temp) ?? "none"}`}>{fmtTemp(r.temp)}</span>
            </div>
          ))}
        </div>

        <WeatherProfile rows={rows} freezingFt={route.freezing_level_ft} />

        <p class="wx-lane wx-lane-snow">
          <Flake />
          Snow on ground <span class="wx-unit">in</span>
          {snowy && (
            <>
              {" · "}
              <span class="wx-lane-new">
                falling <span class="wx-unit">in/hr</span>
              </span>
            </>
          )}
        </p>
        {snowy ? (
          <div class="wx-cols" style={columns(n)}>
            {rows.map((r) => (
              <div key={r.id} class={`wx-col wx-snow${r.isSummit ? " summit" : ""}`}>
                {barPx(r.depth, DEPTH_CAP_IN, DEPTH_MAX_PX) > 0 && (
                  <span class="wx-bar" style={{ height: `${barPx(r.depth, DEPTH_CAP_IN, DEPTH_MAX_PX)}px` }} />
                )}
                {barPx(r.snowfall, RATE_CAP_IN, RATE_MAX_PX) > 0 && (
                  <span class="wx-bar-new" style={{ height: `${barPx(r.snowfall, RATE_CAP_IN, RATE_MAX_PX)}px` }} />
                )}
                <span class={`wx-depth num${r.depth ? "" : " none"}`}>{fmtInches(r.depth)}</span>
                {r.snowfall !== null && r.snowfall > 0 && <span class="wx-rate num">{fmtRate(r.snowfall)}</span>}
              </div>
            ))}
          </div>
        ) : (
          <p class="wx-nosnow">No snow on the ground or falling</p>
        )}

        <div class={`wx-cols wx-names${n >= STAGGER_FROM ? " stagger" : ""}`} style={columns(n)}>
          {rows.map((r) => (
            <div key={r.id} class={`wx-col${r.isSummit ? " summit" : ""}`}>
              <span class="wx-name">{r.short}</span>
              <span class="wx-eta num">{formatClock(r.eta)}</span>
            </div>
          ))}
        </div>
      </div>

      <ul class="sr-only">
        {rows.map((r) => (
          <li key={r.id}>{stopLabel(r)}</li>
        ))}
      </ul>

      <p class="wx-foot">{summarizeRouteWeather(rows)}</p>
    </section>
  );
}
