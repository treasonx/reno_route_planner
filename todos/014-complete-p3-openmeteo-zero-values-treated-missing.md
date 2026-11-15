---
status: complete
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

Option 2 implemented: `_num(row, key, default)` in openmeteo.py returns the default only when the value is absent/null (`is None`), so 0 is preserved for freezing level, precipitation, probability, weather code and snow depth.

## Technical Details

**Affected files:** backend/src/passcheck/sources/openmeteo.py

## Acceptance Criteria

- [x] 0 values preserved; test covers it.

## Work Log

### 2026-11-15 - Code review of PR #1
- Found by the /workflows:review agents on branch feat/pass-check-app.

### 2026-11-15 - Resolved (backend sources/corridors/security)
- Added _num helper; tests test_openmeteo_keeps_zero_values (freezing level 0 stays 0) and test_openmeteo_missing_optional_uses_default.
- `uv run pytest tests/test_merge_and_sources.py tests/test_scheduler.py` passes; ruff + pyright strict clean on touched files.

## Resources

- PR: https://github.com/treasonx/reno_route_planner/pull/1
