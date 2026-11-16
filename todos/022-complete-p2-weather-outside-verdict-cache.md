---
status: complete
priority: p2
issue_id: "022"
tags: [code-review, performance, architecture]
dependencies: []
---

# Per-stop weather is computed inside the verdict cache

## Problem Statement

`Planner.route_eval` (the verdict cache) now also builds per-stop weather. `route_eval` runs for
every hour scanned by the day view, `next_go` and `_run_end`, so one plan makes ~4,550
`weather_at` calls while only 600 values reach the response. Weather never affects a verdict.

## Findings

- `backend/src/passcheck/planner.py` `RouteEval.weather` / `freezing_level_ft`, built in `route_eval`.
- `StopWeather.eta` is never serialized (the frontend computes `depart + minutes`).
- Freezing level is interpolated at every stop but only the summit's value is used.

## Proposed Solutions

### Option 1: Compute weather in `hour_plan` only (`HourPlan.weather[route]`, `HourPlan.freezing_level[route]`). Drop `eta` and per-stop freezing level. Effort: Small. Risk: Low.

### Option 2: Compute in `schemas._route_out`. Effort: Small. Risk: Medium (schema layer reaching into conditions).

## Recommended Action

Option 1 implemented (see Work Log).

## Technical Details

- planner.py, schemas.py, tests/test_planner.py

## Acceptance Criteria

- [ ] `RouteEval` no longer carries weather
- [ ] weather computed once per (route, shown departure)
- [ ] golden unchanged in values

## Work Log

- 2026-11-16: found by code-simplicity review of PR #9.

## Resources

- PR #9
- 2026-11-16: resolved in PR #9 (Option 1).
