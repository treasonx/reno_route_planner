---
title: "feat: Weather along the route tile"
type: feat
date: 2026-11-16
---

# ✨ feat: Weather along the route tile

## Enhancement Summary

**Deepened on:** 2026-11-16 · **Reviewers:** kieran-python, kieran-typescript, code-simplicity
(+ edge-case flow analysis). Decisions below **override** the original sections where they differ.

### Final decisions
1. **Payload shape** — `RouteOut.weather: list[StopWeatherOut]` with
   `{id, temp_f: int|None, snow_depth_in: float|None, snowfall_in_hr: float|None}` and
   `RouteOut.freezing_level_ft: int|None`. No per-stop `eta` in the payload: `StopOut` gains
   `minutes` (fixed per direction) and the frontend computes `depart + minutes` (formatted with
   the shared `formatTime`, which handles DST via the absolute instant).
2. **Planner** — `RouteEval.weather: tuple[StopWeather, ...]` (not `.stops`, which already means
   `Stop` on `Corridor`); `StopWeather` frozen+slots; built in `route_eval` (already cached per
   route,t0) with **no extra cache** (an `(id, hour)` key would be wrong — values depend on the
   exact minute). `_lerp` is a module-level function (ruff E731).
3. **Missing hours** — lerp temp/depth when both hours exist; if only one exists use it; both
   missing → `None` fields. Exact-hour arrival uses that hour only. Snowfall = max of the hours
   (Open-Meteo `snowfall` at H is the total for the hour before H, so `max` is conservative and
   matches the verdict). Planner never nulls stale data; dimming is the UI's job.
4. **Freezing level** — `HourlyPoint.freezing_level_ft: float` (required; the source already
   fills a 99,999 m sentinel). Route value = summit stop's lerped value, rounded to int; the UI
   hides the line when it is above/below the drawn profile range (covers the sentinel).
5. **Rounding (API boundary, one converter)** — temp → int; depth → 1 decimal; snowfall → 1
   decimal but any value > 0 becomes at least 0.1 so the tile never shows 0 while the verdict
   reports snow. The UI colours the pill from the **rounded** number it shows (≤32 blue).
   Missing Open-Meteo `snow_depth` is already 0 upstream; accepted (modelled field anyway).
6. **Stops** — `StopOut` gains `short_label` (Point `short_name: str = ""` keyword + property
   falling back to `name`, mirroring `peak_name/peak_label`), `minutes`, `is_summit`.
7. **Frontend** — `RouteWeather` placed right after `RouteDetail` in `.col-side` (both layouts).
   Props `{corridor, route: RouteOut, depart, stale}`. Pure helpers in `lib/weather.ts`:
   `buildStopRows` (join by id), `profilePoints`, `freezeLinePct`, `barPx`, `tempTone`,
   `stopLabel`, `summarizeRouteWeather`. Null ≠ 0 everywhere ("–" vs "0″"); no truthiness checks.
8. **Accessibility** — visual block `aria-hidden`; a visually hidden `<ul>` with one sentence per
   stop; no extra `aria-live` (Hero already announces).
9. **Footer** (weather only, never "clear"/"safe"): contiguous cold run → "Below freezing from X
   to Y"; broken run → "Below freezing at X, Y"; single → "at X"; none → "Above freezing" (only
   if no stop is null); deepest snow (first in driving order on ties) or "No snow on the ground";
   all null → "No forecast for this trip"; > half null → "Forecast doesn't reach this far".
10. **Width** — 10 stops at 360 px: no "/hr" in cells (unit lives in the lane label), stagger
    names when `n > 7` (named constant) with nowrap overflow into the empty neighbour slot.
11. **Tests** — backend: lerp fraction, exact hour w/ next missing, one/both missing, max rate,
    beyond horizon, invariants per direction×route (len, summit minutes), SAC→RENO I-80 Donner
    at +85 min, rounding/trace, short_label fallback; regenerate golden + `api.gen.ts` +
    `frontend/src/__fixtures__/plan.json`. Frontend: helper table tests incl. every footer
    variant, tile renders listitems in order, "–" vs "0″", 32/33 tone, stale class, stagger
    class, App: tile follows the highway selector and the pager. Run `npm run budget`.

### Considered and not taken
- Dropping the profile / freezing line (simplicity reviewer): kept because the user picked the
  profile design; both are cheap with the decisions above.

## Overview

Add a "Weather on {highway}" card that shows, for the **selected highway** and **selected
departure time**, the conditions at each stop **at the time you pass it**: air temperature,
snow on the ground, and how hard it is snowing. Approved mockup (v3):
https://claude.ai/artifact/HL7QDjSnnmJG6MzGiyAEuE

## Problem Statement / Motivation

The verdict says GO / CAUTION / NO GO and the caption names the problem, but drivers also want
the raw picture: "how cold is it at Donner when I get there, and how much snow is up there?"
We already fetch every number needed (Open-Meteo `temperature_2m`, `snowfall`, `snow_depth`,
`freezing_level_height` for every stop, hourly) and already compute arrival times per stop for
the verdict. The tile just exposes them.

## Proposed Solution

### Design (from the approved mockup)

```
Weather on I-80                         Leaving 7 AM · as you pass
🌡 AIR TEMP °F
 (38°) (29°) (24°) (27°) (30°) (41°) (54°)      pills: blue ≤32, orange >32
 ────── evenly spaced elevation profile ──────  dots per stop, summit larger
 - - - - - - - freezing level - - - - - - - -   dashed line (summit freezing level)
❄ SNOW ON GROUND in · FALLING in/hr
   ▮     █     ▮     ▮                          white bar = depth, striped = rate
   6″   18″   12″    8″
  0.2/hr 0.4/hr ...
 Reno Truckee Donner Kingvale Yuba Gap Colfax Sac
 7:00  7:35   7:50   7:57    8:08    8:32  9:15
──────────────────────────────────────────────
Below freezing from Truckee to Yuba Gap · deepest snow 18″ at Donner
```

- One column per stop (CSS grid `repeat(n, minmax(0,1fr))`), so numbers never overlap; names
  stagger onto two rows when a route has more than 7 stops (US-50 has 10).
- Stops are evenly spaced in this tile (not by distance); the route card above keeps distances.
- Separate labelled lanes (temp above the profile, snow below) with distinct shapes and colors
  — the fix for "hard to tell temp from accumulation".
- Placement: directly under `RouteDetail`, on phone and in the desktop left column.
- Changes with the highway selector and the departure pager, like everything else.

### Data semantics

For departure `t0`, stop `s` with offset `s.minutes`, arrival `ta = t0 + s.minutes`:

| Field | Value at `ta` | Why |
|---|---|---|
| `eta` | `ta` (Pacific) | shown under the stop name |
| `temp_f` | linear interpolation between `floor_hour(ta)` and `+1h` (or the exact hour) | smooth, honest |
| `snow_depth_in` | linear interpolation, same hours | |
| `snow_rate_in` | **max** of the two hours' `snowfall` (in/hr) | conservative, matches the verdict which checks both hours |
| freezing level (route-level) | summit's `freezing_level_ft` at summit arrival | one dashed line, not per stop |

If either hour is missing for a stop, that stop's fields are `null` and render as "–" (never a
made-up number). If the forecast is stale the tile still shows numbers, dimmed, like the hero.

## Technical Approach

### Backend

1. **`backend/src/passcheck/domain.py`** — add `freezing_level_ft: float | None = None` to
   `HourlyPoint` (default keeps existing constructors/tests valid).
2. **`backend/src/passcheck/merge.py`** — `derive_hours` copies `r.freezing_level_ft`.
3. **`backend/src/passcheck/corridors.py`** — add `short_name` to `Point` (e.g. "Donner",
   "Tahoe", "Twin Bridges", "Placerville") for narrow columns; default to `name`.
4. **`backend/src/passcheck/planner.py`**
   - `@dataclass StopWeather(eta, temp_f, snow_depth_in, snow_rate_in)` (floats or `None`).
   - `RouteEval` gains `stops: tuple[StopWeather, ...]` (aligned with `corridor.stops`) and
     `freezing_level_ft: float | None`.
   - `Planner._weather_at(stop, arrival)` — pure lookup on `conditions.hours`, cached like
     `_point_at`. Built inside `route_eval`, so it shares the existing per-(route, t0) cache.
5. **`backend/src/passcheck/schemas.py`** — `StopWeatherOut {eta, temp_f, snow_depth_in,
   snow_rate_in}`; `RouteOut.stops: list[StopWeatherOut]`, `RouteOut.freezing_level_ft`;
   `StopOut.short_name`. Round on output: temp → int, depth → int inches, rate → 0.1 in/hr.
6. Regenerate golden (`UPDATE_GOLDEN=1`) and `frontend/src/api.gen.ts` (CI drift check).

```python
# planner.py (sketch)
def _weather_at(self, stop: Stop, arrival: datetime) -> StopWeather:
    lo = floor_hour(arrival)
    hours = self.ctx.conditions.hours
    a = hours.get((stop.point.id, lo))
    b = a if arrival == lo else hours.get((stop.point.id, lo + HOUR))
    if a is None or b is None:
        return StopWeather(arrival, None, None, None)
    f = (arrival - lo) / HOUR
    lerp = lambda x, y: x + (y - x) * f
    return StopWeather(arrival, lerp(a.temp_f, b.temp_f),
                       lerp(a.snow_depth_in, b.snow_depth_in), max(a.snow_in, b.snow_in))
```

Payload: 24 hours × 3 routes × ~8 stops ≈ 600 small objects; ~25 KB raw, a few KB gzipped,
served from the existing ETag/LRU cache. Acceptable.

### Frontend

1. **`frontend/src/components/RouteWeather.tsx`** (new) — props `{plan, hour, route}`; renders
   card head, temp lane, profile (absolute-positioned SVG with `preserveAspectRatio="none"` +
   `vector-effect: non-scaling-stroke`, HTML dots at the same % coordinates), freezing line,
   snow lane, names + ETAs, footer.
2. **`frontend/src/lib/weather.ts`** (new, pure) — `summarize(stops, names)` → footer text:
   - "Below freezing from {first ≤32 stop} to {last ≤32 stop}" / "Above freezing the whole way"
   - "deepest snow {n}″ at {stop}" / "no snow on the ground"
   - "snowing at {stop}" when any rate > 0 (optional, only if short)
   - bar scales (depth cap 36″, rate cap 1 in/hr), temp class.
3. **`frontend/src/App.tsx`** — render `<RouteWeather>` after `<RouteDetail>` (both layouts).
4. **`frontend/src/theme.css`** — tile styles using existing tokens; add `--snow`,
   `--snow-new`, `--cold`, `--warm` tokens.
5. Accessibility: each column gets an `aria-label` like "Donner Summit, 7:50 AM: 24°F, 18
   inches on the ground, snowing 0.4 inches per hour"; the visual lanes are `aria-hidden`.
   Lane labels are real text. Respect reduced motion (no animation planned).

## Acceptance Criteria

- [ ] Tile shows every stop of the selected highway, in driving order for the chosen direction
- [ ] Values are for the arrival time at each stop (same offsets as the verdict); ETA shown
- [ ] Changing highway or departure time (including another day) updates the tile
- [ ] Temp pill blue at ≤32 °F, orange above; snow depth bar + falling rate bar; "–" for missing
- [ ] Freezing-level dashed line uses the summit's freezing level at summit arrival; hidden
      when unknown or above the profile's top
- [ ] Footer summary sentence correct for: all above freezing, no snow, partial freezing
- [ ] No overlapping text at 360 px for US-50 (10 stops); same tile on desktop left column
- [ ] Screen-reader label per stop
- [ ] Backend tests: interpolation, exact hour, missing hour → None, rate = max, direction
      reversal, freezing level; golden updated
- [ ] Frontend tests: renders stops/ETAs, summary variants, missing values, route switch
- [ ] JS bundle stays within the 30 KB budget; pyright strict, ruff, eslint, tsc clean

## Dependencies & Risks

- `snow_depth` from Open-Meteo is modelled, not measured; label stays "Snow on ground" with no
  claim of accuracy. Acceptable for personal use.
- Interpolating depth across an hour is cosmetic; max rate keeps snowfall conservative.
- `api.gen.ts` must be regenerated or CI fails.

## References

- Mockup: https://claude.ai/artifact/HL7QDjSnnmJG6MzGiyAEuE
- Arrival-time logic: `backend/src/passcheck/planner.py` (`_point_at`, `route_eval`)
- Forecast fields: `backend/src/passcheck/sources/openmeteo.py`, `merge.derive_hours`
- Route card pattern: `frontend/src/components/RouteDetail.tsx`, `RouteProfile.tsx`
- Previous PRs: #6 (highway selector), #8 (I-80 preference)
