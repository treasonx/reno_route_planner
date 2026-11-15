---
status: pending
priority: p2
issue_id: "019"
tags: [code-review, safety, security]
dependencies: []
---

# NaN/Infinity from upstream produces GO (fail-open)

## Problem Statement

`json.loads` accepts NaN/Infinity and every threshold comparison with NaN is False, so `point_verdict(temp=nan, snow=nan)` returns GO; a missing hour correctly returns CAUTION.

## Findings

- `sources/openmeteo.py` row parsing; `verdict.py` comparisons (confirmed by the security reviewer). Same gap for lat/lon in live sources.

## Proposed Solutions

### Option 1: **Skip non-finite rows** (`math.isfinite`) so they become 'No forecast data' (CAUTION); drop live observations with non-finite coordinates. Effort: Small. Risk: Low.

### Option 2: **Reject NaN at JSON parse** with `parse_constant` raising. Effort: Small. Risk: Low (fails whole source).

## Recommended Action

_(Filled during triage.)_

## Technical Details

**Affected files:** backend/src/passcheck/sources/openmeteo.py, backend/src/passcheck/verdict.py

## Acceptance Criteria

- [ ] NaN/Inf values never yield GO; tests cover it.

## Work Log

### 2026-11-15 - Code review of PR #1
- Found by the /workflows:review agents on branch feat/pass-check-app.

## Resources

- PR: https://github.com/treasonx/reno_route_planner/pull/1
