---
status: complete
priority: p1
issue_id: "011"
tags: [code-review, safety, caching]
dependencies: []
---

# Cached plans can miss live chain controls for up to an hour

## Problem Statement

The plan cache key uses `floor_hour(now)` but `segment_verdict` compares arrivals with the exact `now` for the 3 h live window. A plan cached at 10:00 ignores live R-2 for a 13:35 arrival; at 10:40 the arrival is within 3 h but the cached GO is still served.

## Findings

- `backend/src/passcheck/api.py` cache key vs `verdict.py` `near_term`.

## Proposed Solutions

### Option 1: **Use the same time basis**: evaluate the live window against `floor_hour(now)` (and include a whole extra hour: `arrival - now_hour <= 3h + 1h` is conservative). Effort: Small. Risk: Low.

### Option 2: **Finer cache bucket** (5 min). Effort: Small. Risk: Low.

## Recommended Action

Option 1. The live window is now measured from `floor_hour(now)` (same basis as the cache key) and includes the whole current hour: `verdict.in_live_window` = `arrival - floor_hour(now) <= LIVE_OVERRIDE_HOURS + 1h`. `floor_hour` moved to `domain.py` so `verdict.py` can use it. Tests: `test_verdict.py::test_live_window_depends_only_on_current_hour` (0/1/40/59 min past the hour), `test_planner.py::test_live_window_uses_cache_hour_basis` (plans at NOW and NOW+40min with the same live R-2 are identical). Existing window tests updated to the new boundary. The golden changes only in one caption that now includes the live R-2 (coordinator to regenerate).

## Technical Details

**Affected files:** backend/src/passcheck/planner.py, backend/src/passcheck/verdict.py, backend/src/passcheck/api.py

## Acceptance Criteria

- [ ] Plans built at NOW and NOW+40min with the same live data give identical live verdicts.
- [ ] Test covers it.

## Work Log

### 2026-11-15 - Code review of PR #1
- Found by the /workflows:review agents on branch feat/pass-check-app.

### 2026-11-15 - Resolved
- Implemented as described in Recommended Action. ruff, pyright strict and pytest pass (except `test_plan_matches_golden`, pending golden regeneration by the coordinator).

## Resources

- PR: https://github.com/treasonx/reno_route_planner/pull/1
