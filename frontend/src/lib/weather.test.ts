import { describe, expect, it } from "vitest";

import type { CorridorOut, RouteOut } from "../types";
import {
  type StopRow,
  barPx,
  buildStopRows,
  elevationDomain,
  etaFor,
  fmtInches,
  inchWords,
  formatClock,
  freezeLinePct,
  stopLabel,
  summarizeRouteWeather,
  tempTone,
  yPct,
} from "./weather";

const row = (name: string, temp: number | null, depth: number | null = 0, snowfall: number | null = 0): StopRow => ({
  id: name.toLowerCase(),
  name,
  short: name,
  elevationFt: 5000,
  isSummit: false,
  eta: "2026-11-15T15:50:00Z",
  temp,
  depth,
  snowfall,
});

describe("weather helpers", () => {
  it.each([
    [32, "cold"],
    [33, "warm"],
    [-12, "cold"],
    [null, null],
  ] as const)("tempTone(%s) -> %s", (t, tone) => {
    expect(tempTone(t)).toBe(tone);
  });

  it.each([
    [null, "–"],
    [0, "0″"],
    [0.3, "0.3″"],
    [18.4, "18″"],
  ] as const)("fmtInches(%s) -> %s", (d, s) => {
    expect(fmtInches(d)).toBe(s);
  });

  it("keeps zero and unknown apart in bar lengths, with a visible minimum", () => {
    expect(barPx(null, 36, 30)).toBe(0);
    expect(barPx(0, 36, 30)).toBe(0);
    expect(barPx(0.1, 36, 30)).toBe(3);
    expect(barPx(72, 36, 30)).toBe(30);
  });

  it("hides the freezing line when unknown or above the profile", () => {
    const d = elevationDomain([4505, 7056, 30]);
    expect(freezeLinePct(null, d)).toBeNull();
    expect(freezeLinePct(328084, d)).toBeNull();
    expect(freezeLinePct(7420, d)).toBeCloseTo(yPct(7420, d)); // just above Donner: still drawn
    expect(yPct(7420, d)).toBeLessThan(yPct(7056, d));
  });

  it("computes ETAs from the departure and formats them as a clock", () => {
    expect(etaFor("2026-11-15T07:00:00-08:00", 50)).toBe("2026-11-15T15:50:00.000Z");
    const sevenAm = "2026-11-15T15:00:00Z";
    expect(formatClock("2026-11-15T15:50:00Z", sevenAm)).toBe("7:50");
    // Crossing noon / midnight adds a compact period so "1:15" can't read as before "10:00".
    expect(formatClock("2026-11-15T21:15:00Z", "2026-11-15T18:00:00Z")).toBe("1:15p");
    expect(formatClock("2026-11-16T09:50:00Z", "2026-11-16T07:00:00Z")).toBe("1:50a");
    expect(formatClock("2026-11-15T19:45:00Z", "2026-11-15T18:00:00Z")).toBe("11:45");
  });

  it("joins stops and weather by id, in the corridor's driving order", () => {
    const corridor = {
      name: "I-80",
      summit: "Donner Summit",
      towns: [],
      stops: [
        { id: "sacramento", name: "Sacramento", short_label: "Sac", x: 0, y: 0, elevation_ft: 30, peak_label: "", minutes: 0, is_summit: false },
        { id: "donner", name: "Donner Summit", short_label: "Donner", x: 0, y: 0, elevation_ft: 7056, peak_label: "", minutes: 85, is_summit: true },
      ],
    } as CorridorOut;
    const route = {
      weather: [
        { id: "donner", temp_f: 24, snow_depth_in: 18, snowfall_in_hr: 0.4 },
        { id: "sacramento", temp_f: 54, snow_depth_in: 0, snowfall_in_hr: 0 },
      ],
    } as RouteOut;
    const rows = buildStopRows(corridor, route, "2026-11-15T07:00:00-08:00");
    const depart = "2026-11-15T07:00:00-08:00";
    expect(rows.map((r) => [r.short, r.temp, formatClock(r.eta, depart)])).toEqual([
      ["Sac", 54, "7:00"],
      ["Donner", 24, "8:25"],
    ]);
    expect(rows[1]?.isSummit).toBe(true);
  });

  it("reads one sentence per stop, saying when there is no forecast", () => {
    expect(stopLabel(row("Donner Summit", 24, 18, 0.4))).toBe(
      "Donner Summit, 7:50 AM: 24°F, 18 inches of snow on the ground, snowing 0.4 inches per hour",
    );
    expect(stopLabel(row("Reno", 38))).toBe("Reno, 7:50 AM: 38°F, no snow on the ground");
    expect(stopLabel(row("Sacramento", null, null, null))).toBe("Sacramento, 7:50 AM: no forecast");
  });
});

describe("summarizeRouteWeather", () => {
  it.each([
    ["contiguous cold run", [row("Reno", 38), row("Truckee", 29, 6), row("Donner", 24, 18), row("Colfax", 41)],
      "Below freezing from Truckee to Donner · deepest snow 18″ at Donner"],
    ["broken run", [row("Spooner", 25, 14), row("Tahoe", 34, 10), row("Echo", 23, 14)],
      "Below freezing at Spooner, Echo · deepest snow 14″ at Spooner"],
    ["single stop", [row("Reno", 38), row("Donner", 31), row("Sac", 50)],
      "Below freezing at Donner · no snow on the ground"],
    ["all warm", [row("Reno", 40), row("Sac", 55)], "Above freezing the whole way · no snow on the ground"],
    ["all cold", [row("Truckee", 28), row("Donner", 24)], "Below freezing the whole way · no snow on the ground"],
    ["many broken", [row("A", 30), row("B", 40), row("C", 30), row("D", 40), row("E", 30), row("F", 30), row("G", 40)],
      "Below freezing at 4 stops · no snow on the ground"],
    ["snowing on bare ground", [row("Reno", 38), row("Donner", 33, 0, 0.5), row("Sac", 50)],
      "Above freezing the whole way · no snow on the ground · snowing at Donner"],
    ["sparse depth", [row("Reno", 38, 0), row("Donner", 33, null), row("Sac", 50, null)],
      "Above freezing the whole way · no snow on the ground where forecast"],
    ["some missing", [row("Reno", 40), row("Truckee", 41), row("Sac", null, null, null)],
      "Above freezing where forecast · no snow on the ground where forecast"],
    ["mostly missing", [row("Reno", 40), row("A", null, null), row("B", null, null)], "Forecast doesn't reach this far"],
    ["all missing", [row("Reno", null, null), row("Sac", null, null)], "No forecast for this trip"],
  ] as const)("%s", (_case, rows, expected) => {
    expect(summarizeRouteWeather(rows)).toBe(expected);
  });

  it("spells out inches for screen readers", () => {
    const rows = [row("Truckee", 29, 6), row("Donner", 24, 18)];
    expect(summarizeRouteWeather(rows, inchWords)).toBe("Below freezing the whole way · deepest snow 18 inches at Donner");
  });
});
