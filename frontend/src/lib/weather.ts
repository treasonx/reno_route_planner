import type { CorridorOut, RouteOut } from "../types";
import { formatTime } from "./verdict";

/** One stop of the selected highway with the forecast for when you pass it. */
export interface StopRow {
  id: string;
  name: string;
  short: string;
  elevationFt: number;
  isSummit: boolean;
  eta: string; // ISO instant
  temp: number | null; // °F, already rounded by the API
  depth: number | null; // inches on the ground
  snowfall: number | null; // inches per hour
}

const FREEZING_F = 32;
/** From this many stops, names alternate between two rows so they fit at phone width. */
export const STAGGER_FROM = 7;

const clockFmt = new Intl.DateTimeFormat("en-US", {
  timeZone: "America/Los_Angeles",
  hour: "numeric",
  minute: "2-digit",
});

const clockParts = (iso: string) => {
  const parts = clockFmt.formatToParts(new Date(iso));
  const hm = parts
    .filter((p) => p.type === "hour" || p.type === "minute" || (p.type === "literal" && p.value === ":"))
    .map((p) => p.value)
    .join("");
  return { hm, period: parts.find((p) => p.type === "dayPeriod")?.value ?? "" };
};

/**
 * "7:50" in Pacific time for a stop's column. The AM/PM is left off while it matches the
 * departure's, and shown compactly ("1:15p") once the trip crosses noon or midnight.
 */
export const formatClock = (iso: string, departIso: string): string => {
  const { hm, period } = clockParts(iso);
  return period === clockParts(departIso).period ? hm : `${hm}${period.charAt(0).toLowerCase()}`;
};

export const etaFor = (depart: string, minutes: number): string =>
  new Date(Date.parse(depart) + minutes * 60_000).toISOString();

/** Joins the corridor's stops with the route's per-stop weather by id, in driving order. */
export function buildStopRows(corridor: CorridorOut, route: RouteOut, depart: string): StopRow[] {
  const byId = new Map(route.weather.map((w) => [w.id, w]));
  return corridor.stops.map((s) => {
    const w = byId.get(s.id);
    return {
      id: s.id,
      name: s.name,
      short: s.short_label,
      elevationFt: s.elevation_ft,
      isSummit: s.is_summit,
      eta: etaFor(depart, s.minutes),
      temp: w?.temp_f ?? null,
      depth: w?.snow_depth_in ?? null,
      snowfall: w?.snowfall_in_hr ?? null,
    };
  });
}

export const tempTone = (t: number | null): "cold" | "warm" | null =>
  t === null ? null : t <= FREEZING_F ? "cold" : "warm";

/** Bar length for a value: 0 for none/unknown, a visible minimum for any amount. */
export const barPx = (value: number | null, cap: number, maxPx: number): number =>
  value === null || value <= 0 ? 0 : Math.max(3, (Math.min(value, cap) / cap) * maxPx);

export const fmtTemp = (t: number | null): string => (t === null ? "–" : `${t}°`);

/** "0.3" under an inch, whole inches above. */
const inchNumber = (d: number): string => (d > 0 && d < 1 ? d.toFixed(1) : String(Math.round(d)));

export const fmtInches = (d: number | null): string => (d === null ? "–" : `${inchNumber(d)}″`);

/** Spelled-out inches for screen readers ("″" reads aloud as "double prime"). */
export const inchWords = (d: number): string => {
  const n = inchNumber(d);
  return `${n} ${n === "1" ? "inch" : "inches"}`;
};

export const fmtRate = (r: number | null): string => (r === null ? "–" : r.toFixed(1));

/** Vertical scale shared by the profile and the freezing line (percent from the top). */
export interface ElevationDomain {
  top: number; // feet drawn at TOP_PCT
}
const TOP_PCT = 10;
const BOTTOM_PCT = 100;

/** Headroom above the highest stop, so a freezing level just above the summit still shows. */
const HEADROOM = 1.25;

export const elevationDomain = (elevations: readonly number[]): ElevationDomain => ({
  top: Math.max(1000, ...elevations) * HEADROOM,
});

export const yPct = (ft: number, d: ElevationDomain): number =>
  BOTTOM_PCT - (Math.max(0, ft) / d.top) * (BOTTOM_PCT - TOP_PCT);

/** Evenly spaced points (one column per stop), as percentages. */
export const profilePoints = (elevations: readonly number[], d: ElevationDomain) =>
  elevations.map((e, i) => ({ x: ((i + 0.5) / elevations.length) * 100, y: yPct(e, d) }));

/** Where to draw the freezing level, or null when unknown or above the drawn range. */
export const freezeLinePct = (ft: number | null, d: ElevationDomain): number | null =>
  ft === null || ft < 0 || ft > d.top ? null : yPct(ft, d);

const hasSnow = (r: StopRow): boolean => (r.depth ?? 0) > 0 || (r.snowfall ?? 0) > 0;
export const anySnow = (rows: readonly StopRow[]): boolean => rows.some(hasSnow);

/** Screen-reader sentence for one stop (spelled-out units; "″" reads badly aloud). */
export function stopLabel(r: StopRow): string {
  const head = `${r.name}, ${formatTime(r.eta)}`;
  if (r.temp === null) return `${head}: no forecast`;
  const parts = [`${r.temp}°F`];
  if (r.depth !== null) parts.push(r.depth > 0 ? `${inchWords(r.depth)} of snow on the ground` : "no snow on the ground");
  if (r.snowfall !== null && r.snowfall > 0) parts.push(`snowing ${r.snowfall.toFixed(1)} inches per hour`);
  return `${head}: ${parts.join(", ")}`;
}

/** Below-freezing clause. Only says "from X to Y" when every stop in between is also cold. */
function freezingClause(rows: readonly StopRow[]): string {
  const cold = rows.flatMap((r, i) => (tempTone(r.temp) === "cold" ? [i] : []));
  const first = cold[0];
  const last = cold[cold.length - 1];
  if (first === undefined || last === undefined) {
    return rows.every((r) => r.temp !== null) ? "Above freezing the whole way" : "Above freezing where forecast";
  }
  const name = (i: number) => rows[i]?.name ?? "";
  if (cold.length === rows.length) return "Below freezing the whole way";
  if (cold.length === 1) return `Below freezing at ${name(first)}`;
  if (last - first + 1 === cold.length) return `Below freezing from ${name(first)} to ${name(last)}`;
  if (cold.length > 3) return `Below freezing at ${cold.length} stops`;
  return `Below freezing at ${cold.map(name).join(", ")}`;
}

/** The stop with the largest value (first in driving order on ties), or null if none is > 0. */
function peak(rows: readonly StopRow[], value: (r: StopRow) => number | null): StopRow | null {
  let best: StopRow | null = null;
  for (const r of rows) {
    const v = value(r);
    if (v !== null && v > 0 && (best === null || v > (value(best) ?? 0))) best = r;
  }
  return best;
}

type InchFormat = (d: number) => string;

function snowClauses(rows: readonly StopRow[], inches: InchFormat): string[] {
  const out: string[] = [];
  const deepest = peak(rows, (r) => r.depth);
  if (deepest?.depth != null) out.push(`deepest snow ${inches(deepest.depth)} at ${deepest.name}`);
  else if (rows.every((r) => r.depth !== null)) out.push("no snow on the ground");
  else if (rows.some((r) => r.depth !== null)) out.push("no snow on the ground where forecast");
  const heaviest = peak(rows, (r) => r.snowfall);
  if (heaviest) out.push(`snowing at ${heaviest.name}`);
  return out;
}

/**
 * One weather-only sentence for the footer (never a safety call; the verdict does that).
 * ``inches`` formats depths: the glyph form for display, spelled out for screen readers.
 */
export function summarizeRouteWeather(rows: readonly StopRow[], inches: InchFormat = (d) => `${inchNumber(d)}″`): string {
  const known = rows.filter((r) => r.temp !== null).length;
  if (known === 0) return "No forecast for this trip";
  if (known * 2 < rows.length) return "Forecast doesn't reach this far";
  return [freezingClause(rows), ...snowClauses(rows, inches)].join(" · ");
}
