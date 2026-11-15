---
status: pending
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

_(Filled during triage.)_

## Technical Details

**Affected files:** backend/src/passcheck/planner.py, backend/src/passcheck/verdict.py, backend/src/passcheck/api.py

## Acceptance Criteria

- [ ] Plans built at NOW and NOW+40min with the same live data give identical live verdicts.
- [ ] Test covers it.

## Work Log

### 2026-11-15 - Code review of PR #1
- Found by the /workflows:review agents on branch feat/pass-check-app.

## Resources

- PR: https://github.com/treasonx/reno_route_planner/pull/1
