---
status: complete
priority: p2
issue_id: "026"
tags: [code-review, frontend, correctness]
dependencies: []
---

# Stop ETAs drop AM/PM but trips cross noon and midnight

## Problem Statement

`formatClock` shows "1:15" with no period, assuming the departure's AM/PM. Leaving 10 AM on SR-88
ends at "1:15", which reads as earlier than "10:00".

## Findings

- `frontend/src/lib/weather.ts` `formatClock`; `RouteWeather.tsx` names lane.

## Proposed Solutions

### Option 1: Add a compact period ("1:15p") only when it differs from the departure's period. Effort: Small. Risk: Low.

## Recommended Action

Option 1 implemented (see Work Log).

## Acceptance Criteria

- [ ] 10 AM SR-88 and 11 PM departures show the period after the change; tests added

## Work Log

- 2026-11-16: found by kieran-typescript review of PR #9.

## Resources

- PR #9
- 2026-11-16: resolved in PR #9 (Option 1).
