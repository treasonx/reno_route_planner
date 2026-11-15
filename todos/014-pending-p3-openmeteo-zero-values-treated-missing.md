---
status: pending
priority: p3
issue_id: "014"
tags: [code-review, correctness]
dependencies: []
---

# A freezing level of 0 is treated as missing

## Problem Statement

`row.get(...) or default` replaces a real 0.0 freezing level with 99,999 ft, suppressing snow probability.

## Findings

- `backend/src/passcheck/sources/openmeteo.py:69`.

## Proposed Solutions

### Option 1: **Explicit `is None` checks.** Effort: Small. Risk: Low.

### Option 2: **Helper `num(row, key, default)`.** Effort: Small. Risk: Low.

## Recommended Action

_(Filled during triage.)_

## Technical Details

**Affected files:** backend/src/passcheck/sources/openmeteo.py

## Acceptance Criteria

- [ ] 0 values preserved; test covers it.

## Work Log

### 2026-11-15 - Code review of PR #1
- Found by the /workflows:review agents on branch feat/pass-check-app.

## Resources

- PR: https://github.com/treasonx/reno_route_planner/pull/1
