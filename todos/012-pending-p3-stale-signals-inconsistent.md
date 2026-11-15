---
status: pending
priority: p3
issue_id: "012"
tags: [code-review, consistency, frontend]
dependencies: []
---

# Frontend and backend staleness rules disagree

## Problem Statement

The frontend calls a plan stale after 15 min from `generated_at`, which is frozen in cached responses; the backend uses 30 min live / 6 h forecast. The banner can appear while the server says stale=false, or vice versa.

## Findings

- `frontend/src/hooks/usePlan.ts:13`, `backend/src/passcheck/api.py` cache, `domain.py` constants.

## Proposed Solutions

### Option 1: **Trust `plan.stale`** and only add client staleness for failed refreshes (network errors). Effort: Small. Risk: Low.

### Option 2: **Send snapshot `built_at`** and compute age client-side. Effort: Small. Risk: Low.

## Recommended Action

_(Filled during triage.)_

## Technical Details

**Affected files:** frontend/src/hooks/usePlan.ts

## Acceptance Criteria

- [ ] One definition of stale; banner matches server flag.

## Work Log

### 2026-11-15 - Code review of PR #1
- Found by the /workflows:review agents on branch feat/pass-check-app.

## Resources

- PR: https://github.com/treasonx/reno_route_planner/pull/1
