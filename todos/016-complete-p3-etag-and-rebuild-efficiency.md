---
status: complete
priority: p3
issue_id: "016"
tags: [code-review, performance]
dependencies: []
---

# ETag rarely matches; full re-merge and day plans recomputed needlessly

## Problem Statement

Every live poll rebuilds the whole forecast merge (~40 ms on the event loop) and bumps the version, so ETags change every 5 min; weak/multi-value If-None-Match never matches; day plans are recomputed for every (direction, date) request.

## Findings

- `store.py` _rebuild, `api.py` ETag compare, `planner.py` day_plans (~25 of 30 ms).

## Proposed Solutions

### Option 1: **Cache forecast-derived matrices; rebuild only live on live updates; parse If-None-Match properly; memoize days per (version, direction, hour).** Effort: Medium. Risk: Low.

### Option 2: **Accept** for a personal app. Effort: none.

## Recommended Action

Option 1 (except no ETag stabilisation, see below). `merge.py` split into `derive_forecast` (-> `ForecastMatrix`) and `assemble`; `merge()` keeps its signature. `Store` caches the matrix keyed on the identity of the forecast result objects, so live/hint updates only re-map live data and hints. `If-None-Match` is parsed with weak comparison (`W/`, comma lists, `*`) via `api.etag_matches`. Day plans are memoized in the store per (version, direction, hour, floors, forecast_stale) and shared across `?date=` requests (`build_plan(..., days=...)`). Version still bumps on every live poll on purpose: the cached body's `generated_at` drives the client's 15-minute stale check. Tests: `test_etag_matches`, `test_weak_and_listed_if_none_match_get_304`, `test_live_update_reuses_forecast_matrix`, `test_day_plans_shared_across_dates` (all in test_api.py).

## Technical Details

**Affected files:** backend/src/passcheck/store.py, backend/src/passcheck/api.py

## Acceptance Criteria

- [ ] Live poll doesn't re-derive forecast hours.
- [ ] W/ ETags match.

## Work Log

### 2026-11-15 - Code review of PR #1
- Found by the /workflows:review agents on branch feat/pass-check-app.

### 2026-11-15 - Resolved
- Implemented as described in Recommended Action. ruff, pyright strict and pytest pass (except `test_plan_matches_golden`, pending golden regeneration by the coordinator).

## Resources

- PR: https://github.com/treasonx/reno_route_planner/pull/1
