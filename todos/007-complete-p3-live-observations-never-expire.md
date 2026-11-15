---
status: complete
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

Option 1, with one deliberate deviation: the age used is our **fetch time** (the live source's `last_success`) compared to the rebuild time, not the upstream `LiveObservation.observed_at`. Caltrans `observed_at` is the upstream status timestamp, so an R-2 that has been in force for hours carries an old `observed_at`; filtering on it would silently drop active chain controls. In `Store._rebuild`, live results whose source was last fetched more than `LIVE_STALE_MINUTES` before the rebuild are not merged; the CAUTION floor covers "unknown". Test: `test_api.py::test_old_live_result_is_dropped_on_rebuild`. Residual: the snapshot only changes on a rebuild (any source success), so an expired live result may persist until the next forecast/hint refresh; the near-term floor applies alongside it in that window.

## Technical Details

**Affected files:** backend/src/passcheck/store.py, backend/src/passcheck/merge.py

## Acceptance Criteria

- [ ] Observations older than 30 min no longer escalate verdicts; the floor applies instead.

## Work Log

### 2026-11-15 - Code review of PR #1
- Found by the /workflows:review agents on branch feat/pass-check-app.

### 2026-11-15 - Resolved
- Implemented as described in Recommended Action. ruff, pyright strict and pytest pass (except `test_plan_matches_golden`, pending golden regeneration by the coordinator).

## Resources

- PR: https://github.com/treasonx/reno_route_planner/pull/1
- Plan: docs/plans/2026-11-15-feat-pass-check-app-and-docker-image-plan.md
