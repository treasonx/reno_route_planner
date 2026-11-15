---
status: pending
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

_(Filled during triage.)_

## Technical Details

**Affected files:** backend/src/passcheck/corridors.py

## Acceptance Criteria

- [ ] Label and elevation agree.

## Work Log

### 2026-11-15 - Code review of PR #1
- Found by the /workflows:review agents on branch feat/pass-check-app.

## Resources

- PR: https://github.com/treasonx/reno_route_planner/pull/1
