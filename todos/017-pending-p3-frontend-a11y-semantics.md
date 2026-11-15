---
status: pending
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

_(Filled during triage.)_

## Technical Details

**Affected files:** frontend/src/components/*.tsx

## Acceptance Criteria

- [ ] Screen reader hears which stretch is NO GO.
- [ ] Semantics match behaviour.

## Work Log

### 2026-11-15 - Code review of PR #1
- Found by the /workflows:review agents on branch feat/pass-check-app.

## Resources

- PR: https://github.com/treasonx/reno_route_planner/pull/1
