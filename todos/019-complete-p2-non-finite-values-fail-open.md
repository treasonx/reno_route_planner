---
status: complete
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

Option 1 implemented. openmeteo.parse_location converts every numeric field and drops the hour if any value is not `math.isfinite` (hour becomes "No forecast data" → CAUTION). Caltrans and NDOT drop observations with non-finite lat/lon; NDOT also tolerates NaN/Inf/huge LastUpdated (falls back to now). WU skips non-finite qpfSnow so it yields no hint rather than "no snow". verdict.py was not touched (owned by another agent).

## Technical Details

**Affected files:** backend/src/passcheck/sources/openmeteo.py, backend/src/passcheck/verdict.py

## Acceptance Criteria

- [x] NaN/Inf values never yield GO; tests cover it.

## Work Log

### 2026-11-15 - Code review of PR #1
- Found by the /workflows:review agents on branch feat/pass-check-app.

### 2026-11-15 - Resolved (backend sources/corridors/security)
- Added non-finite checks in sources/openmeteo.py, caltrans.py, ndot.py, wu.py; tests cover every Open-Meteo field × NaN/±Inf, bare NaN tokens in raw JSON, Caltrans NaN/Inf coords, NDOT bad timestamps, WU NaN snow.
- `uv run pytest tests/test_merge_and_sources.py tests/test_scheduler.py` passes; ruff + pyright strict clean on touched files.

## Resources

- PR: https://github.com/treasonx/reno_route_planner/pull/1
