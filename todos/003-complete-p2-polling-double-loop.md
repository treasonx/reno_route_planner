---
status: complete
priority: p2
issue_id: "003"
tags: [code-review, frontend, races]
dependencies: []
---

# Polling can run two loops at once

## Problem Statement

In `usePolling`, `onVisibility` doesn't know whether a tick is still in flight. A slow fetch plus a quick tab switch schedules two timers, giving duplicate polling loops that abort each other's requests.

## Findings

- `frontend/src/hooks/usePolling.ts:18-19` schedules after `await fn()` without clearing the existing timer.
- `:27-28` starts a tick or timer regardless of an in-flight tick.

## Proposed Solutions

### Option 1: **In-flight guard.** Track `inFlight`; `onVisibility` does nothing while a tick runs; always `clearTimeout` before `setTimeout`. Effort: Small. Risk: Low.

### Option 2: **Single scheduler function** that owns the one timer handle. Effort: Small. Risk: Low.

## Recommended Action

Option 1 + 2 combined: one timer handle owned by a `schedule()` helper that always clearTimeouts before setTimeout; an `inFlight` flag makes `tick()` re-entrant-safe and `onVisibility` a no-op while a tick runs (the tick re-arms on settle if visible). Rejections from `fn` are swallowed so the loop survives.

## Technical Details

**Affected files:** frontend/src/hooks/usePolling.ts, frontend/src/hooks/usePolling.test.tsx

## Acceptance Criteria

- [x] Tab-flipping during a slow fetch never produces more than one timer.
- [x] Test with fake timers and a pending promise.

## Work Log

### 2026-11-15 - Code review of PR #1
- Found by the /workflows:review agents on branch feat/pass-check-app.

### 2026-11-15 - Frontend resolution (complete)
- Rewrote `frontend/src/hooks/usePolling.ts` with single timer handle + inFlight guard.
- Added fake-timer tests in `usePolling.test.tsx`: hide/show during a pending fetch yields exactly one loop (fails on old code), and no polling after unmount even with a fetch in flight.
- Verified: `npx tsc --noEmit && npx eslint . && npx vitest run` all pass (24 tests).

## Resources

- PR: https://github.com/treasonx/reno_route_planner/pull/1
- Plan: docs/plans/2026-11-15-feat-pass-check-app-and-docker-image-plan.md
