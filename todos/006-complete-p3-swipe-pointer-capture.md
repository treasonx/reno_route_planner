---
status: complete
priority: p3
issue_id: "006"
tags: [code-review, frontend, ux]
dependencies: []
---

# Swipe misses gestures that leave the card; multi-touch overwrites start

## Problem Statement

`useSwipe` doesn't capture the pointer, so a swipe ending outside the card is lost, and a second finger overwrites the start point.

## Findings

- `frontend/src/hooks/useSwipe.ts:9-21`.

## Proposed Solutions

### Option 1: **setPointerCapture on pointerdown; ignore new pointers while one is active.** Effort: Small. Risk: Low.

### Option 2: **Leave as is** (tabs and keyboard still work). Effort: none.

## Recommended Action

Option 1: `setPointerCapture` on pointerdown (best-effort, try/catch); ignore new pointers while one is active; pointerup/pointercancel only act on the tracked pointer id. Returned handler names unchanged so RoutesCard's spread still works.

## Technical Details

**Affected files:** frontend/src/hooks/useSwipe.ts

## Acceptance Criteria

- [x] Swipes that end outside the card still switch routes.
- [x] A second finger doesn't cancel the first.

## Work Log

### 2026-11-15 - Code review of PR #1
- Found by the /workflows:review agents on branch feat/pass-check-app.

### 2026-11-15 - Frontend resolution (complete)
- Updated `frontend/src/hooks/useSwipe.ts`.
- Added `hooks/useSwipe.test.tsx` (capture, second-finger ignored, pointercancel).
- Verified: `npx tsc --noEmit && npx eslint . && npx vitest run` all pass (24 tests).

## Resources

- PR: https://github.com/treasonx/reno_route_planner/pull/1
- Plan: docs/plans/2026-11-15-feat-pass-check-app-and-docker-image-plan.md
