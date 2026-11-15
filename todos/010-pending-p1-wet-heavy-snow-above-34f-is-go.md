---
status: pending
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

_(Filled during triage.)_

## Technical Details

**Affected files:** backend/src/passcheck/verdict.py, backend/tests/test_verdict.py

## Acceptance Criteria

- [ ] snow_in > 0 never yields GO.
- [ ] Threshold table and hypothesis tests cover it.

## Work Log

### 2026-11-15 - Code review of PR #1
- Found by the /workflows:review agents on branch feat/pass-check-app.

## Resources

- PR: https://github.com/treasonx/reno_route_planner/pull/1
