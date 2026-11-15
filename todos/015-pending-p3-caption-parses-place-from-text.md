---
status: pending
priority: p3
issue_id: "015"
tags: [code-review, correctness, quality]
dependencies: []
---

# Captions split on ' at ' inside free-text descriptions

## Problem Statement

`caption_for` regroups places by splitting on the last ' at ', so live descriptions like 'No chain controls are in effect at this time.' are split wrongly.

## Findings

- `backend/src/passcheck/planner.py` `caption_for`, `_place`.

## Proposed Solutions

### Option 1: **Carry (reason, place) tuples** through Verdict and format once. Effort: Medium. Risk: Low.

### Option 2: **Live reasons use a distinct separator ('near')** and caption_for only groups ' at '. Effort: Small. Risk: Low.

## Recommended Action

_(Filled during triage.)_

## Technical Details

**Affected files:** backend/src/passcheck/planner.py, backend/src/passcheck/verdict.py

## Acceptance Criteria

- [ ] Free-text descriptions are never split.

## Work Log

### 2026-11-15 - Code review of PR #1
- Found by the /workflows:review agents on branch feat/pass-check-app.

## Resources

- PR: https://github.com/treasonx/reno_route_planner/pull/1
