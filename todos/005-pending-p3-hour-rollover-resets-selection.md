---
status: pending
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

_(Filled during triage.)_

## Technical Details

**Affected files:** frontend/src/App.tsx

## Acceptance Criteria

- [ ] A refresh across the hour keeps the selected departure if it still exists.

## Work Log

### 2026-11-15 - Code review of PR #1
- Found by the /workflows:review agents on branch feat/pass-check-app.

## Resources

- PR: https://github.com/treasonx/reno_route_planner/pull/1
- Plan: docs/plans/2026-11-15-feat-pass-check-app-and-docker-image-plan.md
