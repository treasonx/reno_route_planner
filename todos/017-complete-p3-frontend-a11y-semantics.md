---
status: complete
priority: p3
issue_id: "017"
tags: [code-review, accessibility, frontend]
dependencies: []
---

# Accessibility semantics in pager, tabs, profile and 10-day strip

## Problem Statement

Pager is a listbox without arrow-key behaviour; tabpanel lacks aria-labelledby; role=img hides per-stretch verdicts from screen readers; TenDay should be a radiogroup; heading says 10 days but 11 are returned; pager index isn't clamped like App's.

## Findings

- `LeaveAtPager.tsx:16,35-46`, `RoutesCard.tsx:84-124`, `RouteProfile.tsx:19`, `TenDay.tsx:13,26`.

## Proposed Solutions

### Option 1: **Use buttons with aria-pressed for hours and days, aria-labelledby on the panel, per-stretch summary in the SVG label, clamp index, fix heading.** Effort: Small. Risk: Low.

### Option 2: **Full roving-tabindex radiogroups.** Effort: Medium. Risk: Low.

## Recommended Action

Option 1, with tab keyboard fixes: hours become toggle buttons (aria-pressed) in a labelled group; route tabpanel labelled by the selected tab with useId-generated ids, Home/End support and non-wrapping arrows; SVG label lists non-GO stretches; TenDay becomes a radiogroup with heading "10-day outlook"; pager index clamped internally. QuickMap URL extracted to a const in Status.tsx.

## Technical Details

**Affected files:** frontend/src/components/*.tsx

## Acceptance Criteria

- [x] Screen reader hears which stretch is NO GO.
- [x] Semantics match behaviour.

## Work Log

### 2026-11-15 - Code review of PR #1
- Found by the /workflows:review agents on branch feat/pass-check-app.

### 2026-11-15 - Resolved
- LeaveAtPager.tsx: role=listbox/option -> role=group + aria-pressed buttons; index clamped with Math.min(index, hours.length - 1).
- RoutesCard.tsx: useId-based tab/panel ids; tabpanel aria-labelledby selected tab + tabIndex=0; ArrowLeft/Right stop at ends, Home/End added.
- RouteProfile.tsx: aria-label includes "A → B: CAUTION; ..." for non-GO stretches or "All stretches GO."
- TenDay.tsx: role=radiogroup + role=radio/aria-checked; heading "10-day outlook" (labels the section and group).
- Status.tsx: QUICKMAP_URL const.
- App.test.tsx needs `getByText("Next 10 days")` -> `getByText("10-day outlook")` (owned by another agent).

## Resources

- PR: https://github.com/treasonx/reno_route_planner/pull/1
