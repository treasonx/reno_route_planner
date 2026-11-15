---
status: pending
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

_(Filled during triage.)_

## Technical Details

**Affected files:** backend/src/passcheck/store.py, backend/src/passcheck/api.py

## Acceptance Criteria

- [ ] Live poll doesn't re-derive forecast hours.
- [ ] W/ ETags match.

## Work Log

### 2026-11-15 - Code review of PR #1
- Found by the /workflows:review agents on branch feat/pass-check-app.

## Resources

- PR: https://github.com/treasonx/reno_route_planner/pull/1
