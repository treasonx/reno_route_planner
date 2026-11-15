---
status: complete
priority: p3
issue_id: "013"
tags: [code-review, data, consistency]
dependencies: []
---

# Summit labels contradict elevation values

## Problem Statement

Donner 7,214 ft vs label 7,056′; Spooner 7,155 vs 7,146′; Echo 7,401 vs 7,382′. The elevation (from the Caltrans chain-control point / DEM) is what's sent to Open-Meteo, the label is the posted summit.

## Findings

- `backend/src/passcheck/corridors.py` Point definitions.

## Proposed Solutions

### Option 1: **Use posted summit elevations for summit points and derive labels from `elevation_ft`.** Effort: Small. Risk: Low.

### Option 2: **Keep both but document** (sensor site vs signed summit). Effort: Small. Risk: Low.

## Recommended Action

Option 1 implemented. Summit Points now use the posted summit elevations (Donner 7,056, Spooner 7,146, Echo 7,382, Carson Pass 8,574 ft) and `Point.peak_label` is a property derived from `peak_name` + `elevation_ft` (f"{short} {elev:,}′"), so they cannot disagree. golden/plan_reno_sac.json needs regeneration by the coordinator (profile y and forecast elevations changed).

## Technical Details

**Affected files:** backend/src/passcheck/corridors.py

## Acceptance Criteria

- [x] Label and elevation agree.

## Work Log

### 2026-11-15 - Code review of PR #1
- Found by the /workflows:review agents on branch feat/pass-check-app.

### 2026-11-15 - Resolved (backend sources/corridors/security)
- Replaced the peak_label field with peak_name + derived peak_label property in corridors.py; schemas.py consumes it unchanged. Added test_summit_label_matches_elevation and test_only_summits_have_peak_labels.
- `uv run pytest tests/test_merge_and_sources.py tests/test_scheduler.py` passes; ruff + pyright strict clean on touched files.

## Resources

- PR: https://github.com/treasonx/reno_route_planner/pull/1
