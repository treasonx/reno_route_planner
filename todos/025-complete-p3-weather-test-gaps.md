---
status: complete
priority: p3
issue_id: "025"
tags: [code-review, testing]
dependencies: ["022"]
---

# Weather test gaps and snowfall docstring

## Problem Statement

A few behaviours of the weather tile are untested, and the `weather_at` docstring overstates
which hour the snowfall covers on exact-hour arrivals (it matches the verdict's `_point_at`, which
also reads only the exact hour).

## Findings

- No test where only the later hour exists.
- No test pinning the summit freezing level to a non-trivial interpolated value.
- No test of serialized `/api/plan` values (int temps, snowfall > 0 in the fixture storm).
- `short_label` fallback (`truckee` → "Truckee") untested.
- `_tenths` midpoints (0.05, 0.95) unpinned.

## Proposed Solutions

### Option 1: Add the tests; reword the docstring to say exact-hour arrivals read that hour, like the verdict. Effort: Small. Risk: Low.

## Recommended Action

Option 1 implemented (see Work Log).

## Acceptance Criteria

- [ ] Tests listed above added and passing

## Work Log

- 2026-11-16: found by kieran-python review of PR #9.

## Resources

- PR #9
- 2026-11-16: resolved in PR #9 (Option 1).
- Snowfall docstring reworded: exact-hour arrivals read that hour only, like the verdict.
