---
status: complete
priority: p3
issue_id: "005"
tags: [code-review, frontend, ux]
dependencies: []
---

# Hourly rollover resets the user's selected departure

## Problem Statement

`planKey` includes `hours[0].depart`, which moves every hour in 'now' mode, so a background refresh that crosses the hour snaps the selection back to Now.

## Findings

- `frontend/src/App.tsx` selection keyed on planKey.

## Proposed Solutions

### Option 1: **Store the selected depart timestamp** and look it up in the new plan; fall back to default if missing. Effort: Small. Risk: Low.

### Option 2: **Exclude hours[0] from the key in now-mode.** Effort: Small. Risk: Low.

## Recommended Action

Option 1: App stores `{ ctx: direction|date, depart, tab }`. On each plan, the departure is looked up by timestamp; if missing (rolled off) or context changed, fall back to default (now -> 0, day -> 6 AM) and the tab follows the recommendation. The tab is kept only when the departure is found unchanged.

## Technical Details

**Affected files:** frontend/src/App.tsx

## Acceptance Criteria

- [x] A refresh across the hour keeps the selected departure if it still exists.

## Work Log

### 2026-11-15 - Code review of PR #1
- Found by the /workflows:review agents on branch feat/pass-check-app.

### 2026-11-15 - Frontend resolution (complete)
- Updated selection logic in `frontend/src/App.tsx`.
- Added App test: select 9 AM + SR-88 tab, refresh returns an hour-shifted plan -> 9 AM and SR-88 tab remain selected (fails on old code).
- Verified: `npx tsc --noEmit && npx eslint . && npx vitest run` all pass (24 tests).

## Resources

- PR: https://github.com/treasonx/reno_route_planner/pull/1
- Plan: docs/plans/2026-11-15-feat-pass-check-app-and-docker-image-plan.md
