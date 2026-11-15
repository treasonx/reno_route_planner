---
status: complete
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

Option 1. New `domain.Reason(text, place)` (with `__str__` -> "text at place"); `Verdict.reasons` is `tuple[Reason, ...]` plus a `texts` helper. The planner sets `place` on forecast reasons; live reasons (free upstream text) never get a place. `caption_for` groups by the structured place and never parses text. Test: `test_planner.py::test_caption_never_splits_free_text`; existing caption test updated.

## Technical Details

**Affected files:** backend/src/passcheck/planner.py, backend/src/passcheck/verdict.py

## Acceptance Criteria

- [ ] Free-text descriptions are never split.

## Work Log

### 2026-11-15 - Code review of PR #1
- Found by the /workflows:review agents on branch feat/pass-check-app.

### 2026-11-15 - Resolved
- Implemented as described in Recommended Action. ruff, pyright strict and pytest pass (except `test_plan_matches_golden`, pending golden regeneration by the coordinator).

## Resources

- PR: https://github.com/treasonx/reno_route_planner/pull/1
