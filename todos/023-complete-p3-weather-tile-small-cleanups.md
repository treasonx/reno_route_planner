---
status: complete
priority: p3
issue_id: "023"
tags: [code-review, quality]
dependencies: []
---

# Small cleanups in the weather tile

## Problem Statement

Minor duplication and dead code from PR #9.

## Findings

- `frontend/src/App.tsx` repeats the "Now" → "now" leaving label from `RouteDetail.tsx`.
- `frontend/src/lib/weather.ts`: `fmtInches` and `inchWords` duplicate the <1 inch rule.
- `frontend/src/components/RouteWeather.tsx`: `barPx` computed twice per bar.
- `backend/src/passcheck/planner.py` `weather_at`: assert + reassignment for the one-missing-hour case.
- `frontend/src/types.ts`: `StopWeatherOut` export unused.

## Proposed Solutions

### Option 1: Fix each in place (shared `leavingLabel`, one `inchNumber`, compute bar heights once, simplify fallback, drop unused export). Effort: Small. Risk: Low.

## Recommended Action

Option 1 implemented (see Work Log).

## Acceptance Criteria

- [ ] Each item addressed; tests, lint, typecheck pass

## Work Log

- 2026-11-16: found by code-simplicity review of PR #9.

## Resources

- PR #9
- 2026-11-16: resolved in PR #9 (Option 1).
