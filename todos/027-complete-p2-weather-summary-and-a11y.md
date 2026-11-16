---
status: complete
priority: p2
issue_id: "027"
tags: [code-review, frontend, accessibility]
dependencies: []
---

# Weather summary gaps and screen-reader parity

## Problem Statement

The footer and screen-reader list miss some of what the tile shows.

## Findings

- Freezing level only appears inside the aria-hidden visual block.
- Footer uses "″", which reads as "double prime" aloud.
- Summary ignores falling snow (depth 0, snowfall > 0 says "no snow on the ground").
- "No snow on the ground" is claimed when only one stop has depth data.
- All-cold routes read "Below freezing from Reno to Sac" instead of "the whole way".

## Proposed Solutions

### Option 1: Add a freezing-level sr-only item; aria-hidden visual footer + sr twin (or inch words); "snowing at X" clause; coverage rule for depth; "whole way" for all cold. Effort: Small. Risk: Low.

## Recommended Action

Option 1 implemented (see Work Log).

## Acceptance Criteria

- [ ] Each case covered by a summary/component test

## Work Log

- 2026-11-16: found by kieran-typescript review of PR #9.

## Resources

- PR #9
- 2026-11-16: resolved in PR #9 (Option 1).
