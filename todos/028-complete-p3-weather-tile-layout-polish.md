---
status: complete
priority: p3
issue_id: "028"
tags: [code-review, frontend, css]
dependencies: []
---

# Weather tile layout polish

## Problem Statement

Edge-case layout issues at phone width and labelling.

## Findings

- Freezing-line label can poke above the profile when the line is near the top.
- 3-character temps ("-12°", "100°") overflow ~26px pills on US-50 at 360px.
- I-80 (7 stops) doesn't stagger; "Kingvale"/"Yuba Gap" can touch at 360px.
- Region uses aria-label duplicating the h2 (prefer aria-labelledby).
- Freezing line is the summit's but drawn across all stops; label should say "at summit".

## Proposed Solutions

### Option 1: Flip label below the line near the top; nowrap + smaller pill font on narrow screens; stagger from 7 stops; aria-labelledby; "Freezing at summit" label. Effort: Small. Risk: Low.

## Recommended Action

Option 1 implemented (see Work Log).

## Acceptance Criteria

- [ ] Checked at 360px for I-80 and US-50

## Work Log

- 2026-11-16: found by kieran-typescript review of PR #9.

## Resources

- PR #9
- 2026-11-16: resolved in PR #9 (Option 1).
- Freezing-line label moved into the Air temp lane header ("32°F at X′ at summit") instead of flipping under the line, which overlapped the summit dot.
