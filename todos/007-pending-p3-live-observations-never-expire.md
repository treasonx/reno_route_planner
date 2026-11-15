---
status: pending
priority: p3
issue_id: "007"
tags: [code-review, architecture, safety]
dependencies: []
---

# Live chain/closure observations never age out

## Problem Statement

The store merges the last good live result indefinitely; if Caltrans is down for hours, old chain controls keep producing NO GO alongside the CAUTION floor, with no indication of age.

## Findings

- `LiveStatus` has no `observed_at`; `store.py` re-merges old `LiveResult`s on every rebuild.

## Proposed Solutions

### Option 1: **Drop live observations older than the stale window** (the CAUTION floor already covers 'unknown'). Effort: Small. Risk: Low.

### Option 2: **Keep them but label their age** in the caption. Effort: Medium. Risk: Low.

## Recommended Action

_(Filled during triage.)_

## Technical Details

**Affected files:** backend/src/passcheck/store.py, backend/src/passcheck/merge.py

## Acceptance Criteria

- [ ] Observations older than 30 min no longer escalate verdicts; the floor applies instead.

## Work Log

### 2026-11-15 - Code review of PR #1
- Found by the /workflows:review agents on branch feat/pass-check-app.

## Resources

- PR: https://github.com/treasonx/reno_route_planner/pull/1
- Plan: docs/plans/2026-11-15-feat-pass-check-app-and-docker-image-plan.md
