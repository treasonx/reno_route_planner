---
status: pending
priority: p2
issue_id: "004"
tags: [code-review, frontend, races, safety]
dependencies: []
---

# Previous plan renders under the new direction for a frame

## Problem Statement

`usePlan` resets to loading in a `useEffect`, which runs after paint. After swapping direction (or picking a day) the first render shows the old direction's verdicts under the new header. For a safety app, showing Reno→Sac verdicts labelled Sac→Reno, even briefly, is wrong.

## Findings

- `frontend/src/hooks/usePlan.ts:39-43`.

## Proposed Solutions

### Option 1: **Key the state.** Store `key = direction|date` with the state and treat `state.key !== currentKey` as loading during render. Effort: Small. Risk: Low.

### Option 2: **Check `plan.direction` in App** before rendering. Partial: doesn't cover date. Effort: Small. Risk: Low.

## Recommended Action

_(Filled during triage.)_

## Technical Details

**Affected files:** frontend/src/hooks/usePlan.ts, frontend/src/App.tsx

## Acceptance Criteria

- [ ] After a swap, no render pairs the new direction with the old plan.
- [ ] Test asserts the skeleton appears immediately after swap.

## Work Log

### 2026-11-15 - Code review of PR #1
- Found by the /workflows:review agents on branch feat/pass-check-app.

## Resources

- PR: https://github.com/treasonx/reno_route_planner/pull/1
- Plan: docs/plans/2026-11-15-feat-pass-check-app-and-docker-image-plan.md
