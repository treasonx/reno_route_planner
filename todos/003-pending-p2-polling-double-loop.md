---
status: pending
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

_(Filled during triage.)_

## Technical Details

**Affected files:** frontend/src/hooks/usePolling.ts, frontend/src/hooks/usePolling.test.tsx

## Acceptance Criteria

- [ ] Tab-flipping during a slow fetch never produces more than one timer.
- [ ] Test with fake timers and a pending promise.

## Work Log

### 2026-11-15 - Code review of PR #1
- Found by the /workflows:review agents on branch feat/pass-check-app.

## Resources

- PR: https://github.com/treasonx/reno_route_planner/pull/1
- Plan: docs/plans/2026-11-15-feat-pass-check-app-and-docker-image-plan.md
