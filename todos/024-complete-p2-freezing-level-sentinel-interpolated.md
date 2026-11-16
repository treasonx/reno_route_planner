---
status: complete
priority: p2
issue_id: "024"
tags: [code-review, correctness]
dependencies: ["022"]
---

# Freezing-level "missing" sentinel is interpolated as a real height

## Problem Statement

Open-Meteo's missing `freezing_level_height` becomes a 99,999 m sentinel (`sources/openmeteo.py`).
`weather_at` lerps it with a real neighbour hour, producing e.g. 274,000 ft, which hides the
freezing line exactly when a low freezing level matters, and returns a meaningless height.

## Findings

- `backend/src/passcheck/planner.py` `weather_at` freezing level lerp.

## Proposed Solutions

### Option 1: Treat the sentinel as missing for this field: use the real neighbour or None. Effort: Small. Risk: Low.
### Option 2: Make the field Optional through RawHour/HourlyPoint. Effort: Medium (merge._snow_prob relies on the sentinel). Risk: Medium.

## Recommended Action

Option 1 implemented (see Work Log).

## Acceptance Criteria

- [ ] One real hour + one sentinel hour → real value; both sentinel → None
- [ ] Test added

## Work Log

- 2026-11-16: found by kieran-python review of PR #9.

## Resources

- PR #9
- 2026-11-16: resolved in PR #9 (Option 1).
