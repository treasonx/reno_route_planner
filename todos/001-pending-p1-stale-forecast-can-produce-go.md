---
status: pending
priority: p1
issue_id: "001"
tags: [code-review, safety, architecture]
dependencies: []
---

# Stale forecast can still produce GO

## Problem Statement

When every forecast source has failed for more than 6 h, `/api/plan` sets `stale: true` and shows a banner but still computes GO from hours-old data. The plan's acceptance criterion says missing or stale data never produces GO.

## Findings

- `backend/src/passcheck/api.py` ~line 93 computes `stale` but never passes it to the planner.
- `planner.PlanContext` only receives the live floor flags; the forecast staleness is not modelled.
- Plan text contradicts itself (stale section: banner only; acceptance criteria: never GO).

## Proposed Solutions

### Option 1: **Forecast floor in the planner.** Add `forecast_stale: bool` to `PlanContext`; when true every segment is floored at CAUTION with reason "Forecast data is out of date". Pros: simple, consistent with live floor. Cons: none. Effort: Small. Risk: Low.

### Option 2: **Return 503 when stale.** Treat a stale forecast like no data. Pros: simplest. Cons: hides a still-useful (if cautious) view. Effort: Small. Risk: Low.

## Recommended Action

_(Filled during triage.)_

## Technical Details

**Affected files:** backend/src/passcheck/api.py, backend/src/passcheck/planner.py, backend/tests/test_planner.py

## Acceptance Criteria

- [ ] With all forecast sources older than 6 h no route or hour is GO.
- [ ] Reason text explains the forecast is out of date.
- [ ] Test covers it; plan text updated to one rule.

## Work Log

### 2026-11-15 - Code review of PR #1
- Found by the /workflows:review agents on branch feat/pass-check-app.

## Resources

- PR: https://github.com/treasonx/reno_route_planner/pull/1
- Plan: docs/plans/2026-11-15-feat-pass-check-app-and-docker-image-plan.md
