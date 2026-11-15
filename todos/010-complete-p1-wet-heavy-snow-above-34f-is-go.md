---
status: complete
priority: p1
issue_id: "010"
tags: [code-review, safety, correctness]
dependencies: []
---

# Heavy snowfall just above 34°F can return GO

## Problem Statement

`point_verdict` only considers accumulation when temp ≤ 34°F and otherwise relies on probability, so 0.9 in/hr of snow at 35°F with a 10% probability is GO with no reason. Wet snow at 35°F (2 m air temp) is common in the Sierra.

## Findings

- `backend/src/passcheck/verdict.py:42-50` (probed).
- Property tests never vary probability vs snowfall.

## Proposed Solutions

### Option 1: **Any forecast snowfall is at least CAUTION**; ≥ 0.5 in/hr at ≤ 34°F stays NO GO. Effort: Small. Risk: Low.

### Option 2: **Treat ≥ 0.5 in/hr at ≤ 36°F as NO GO.** Effort: Small. Risk: Medium (changes agreed threshold).

## Recommended Action

Option 1. `point_verdict`: >= 0.5 in/hr at <= 34°F stays NO GO; >= 0.5 in/hr above 34°F is CAUTION ("Wet snow X in/hr"); any other snow_in > 0 is CAUTION ("Light snow") regardless of temperature or probability. Threshold table extended (half-inch above 34°F now CAUTION, 0.9 in/hr at 35°F with 10%, trace snow at 45°F, light snow with 0%); new hypothesis tests `test_any_forecast_snow_is_never_go` (varies temp, snow, probability) and `test_higher_probability_never_improves`. Plan doc pseudo-code updated.

## Technical Details

**Affected files:** backend/src/passcheck/verdict.py, backend/tests/test_verdict.py

## Acceptance Criteria

- [ ] snow_in > 0 never yields GO.
- [ ] Threshold table and hypothesis tests cover it.

## Work Log

### 2026-11-15 - Code review of PR #1
- Found by the /workflows:review agents on branch feat/pass-check-app.

### 2026-11-15 - Resolved
- Implemented as described in Recommended Action. ruff, pyright strict and pytest pass (except `test_plan_matches_golden`, pending golden regeneration by the coordinator).

## Resources

- PR: https://github.com/treasonx/reno_route_planner/pull/1
