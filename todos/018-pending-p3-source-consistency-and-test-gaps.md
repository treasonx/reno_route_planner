---
status: pending
priority: p3
issue_id: "018"
tags: [code-review, quality, testing]
dependencies: []
---

# Inconsistent source conventions and test gaps

## Problem Statement

`assert` used for control flow (stripped by python -O); WU parses JSON in fetch; string source names vs enum; WU summits hand-listed; flaky wall-clock benchmark in default test run; frontend tests don't cover day selection, swipe/keys, or keep-last-plan-on-error.

## Findings

- caltrans.py:33, ndot.py:113, wu.py:52,68; tests/test_api.py benchmark; App.test.tsx.

## Proposed Solutions

### Option 1: **Replace asserts with explicit checks; loosen/mark benchmark; add the missing frontend tests.** Effort: Medium. Risk: Low.

### Option 2: **Only fix asserts and the flaky benchmark.** Effort: Small. Risk: Low.

## Recommended Action

_(Filled during triage.)_

## Technical Details

**Affected files:** backend/src/passcheck/sources/*.py, backend/tests/test_api.py, frontend/src/App.test.tsx

## Acceptance Criteria

- [ ] No assert-based control flow in src.
- [ ] Benchmark not flaky; key UI flows tested.

## Work Log

### 2026-11-15 - Code review of PR #1
- Found by the /workflows:review agents on branch feat/pass-check-app.

## Resources

- PR: https://github.com/treasonx/reno_route_planner/pull/1
