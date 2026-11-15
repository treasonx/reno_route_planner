---
status: complete
priority: p3
issue_id: "008"
tags: [code-review, quality, simplicity]
dependencies: []
---

# Duplicated constants, dead fields and a redundant 404 path

## Problem Statement

Small cleanup from the simplicity and architecture reviews: constants are defined twice and can drift; some fields are never read.

## Findings

- `api.py` DAYS_AHEAD / FORECAST_MAX_AGE duplicate planner/domain constants (status vs plan staleness can drift).
- Two /api 404 catch-alls (api.py and main.py spa).
- Unused: `LiveResult.source`, `UpstreamError.source`, `app.state.settings`.
- `security.py` adds RedactingFilter to the root logger and its handler (root filter is redundant).
- `DayPlan.best_route` typed Optional but always set.
- Unreachable `if (!hour)` branch in App.tsx.

## Proposed Solutions

### Option 1: **Apply the listed cleanups** (~50 LOC). Effort: Small. Risk: Low.

### Option 2: **Only dedupe the constants** (the drift risk). Effort: Small. Risk: Low.

## Recommended Action

Backend parts only. `DAYS_AHEAD` is defined once in `planner.py` (API imports it); staleness windows are defined once in `store.py` (`LIVE_MAX_AGE`, `FORECAST_MAX_AGE`, `max_age(kind)`, `SourceState.fresh`) from the `domain` constants, used by status, floors and live expiry. Removed the duplicate `/api/` 404 check from `main.py` `spa` (the API router's catch-all owns it), removed unused `app.state.settings`, made `DayPlan.best_route` / `DayOut.best_route` non-optional. Kept `LiveResult.source` / `UpstreamError.source`. Not done here (owned elsewhere): `security.py` root filter, `frontend/src/App.tsx` unreachable branch, and regenerating `frontend/src/api.gen.ts` (DayOut.best_route is no longer nullable).

## Technical Details

**Affected files:** backend/src/passcheck/api.py, store.py, security.py, planner.py, schemas.py, sources/base.py, frontend/src/App.tsx

## Acceptance Criteria

- [ ] One definition each for day horizon and staleness windows.
- [ ] Lint, pyright, tests pass.

## Work Log

### 2026-11-15 - Code review of PR #1
- Found by the /workflows:review agents on branch feat/pass-check-app.

### 2026-11-15 - Frontend resolution (partial: frontend only)
- Frontend part: the `if (!hour)` branch is NOT provably unreachable — `PlanOut.hours` is a plain `list[HourOut]` with no min length and `planner.departures(day)` could in principle be empty, and `noUncheckedIndexedAccess` makes the type `HourOut | undefined`. Kept it as an explicit safe fallback (no verdict, DataUnavailable + footer) with a comment, and removed the redundant `Math.min` clamp now that the index comes from a lookup.
- Dropped SSR guards from `frontend/src/hooks/useMediaQuery.ts` (client-only SPA).
- Backend parts (constants dedupe, 404 catch-alls, unused fields, logger filter, best_route Optional) not handled here — left pending.
- Verified: `npx tsc --noEmit && npx eslint . && npx vitest run` all pass (24 tests).

### 2026-11-15 - Resolved
- Implemented as described in Recommended Action. ruff, pyright strict and pytest pass (except `test_plan_matches_golden`, pending golden regeneration by the coordinator).

## Resources

- PR: https://github.com/treasonx/reno_route_planner/pull/1
- Plan: docs/plans/2026-11-15-feat-pass-check-app-and-docker-image-plan.md
