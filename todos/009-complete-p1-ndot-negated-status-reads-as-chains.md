---
status: complete
priority: p1
issue_id: "009"
tags: [code-review, safety, correctness]
dependencies: []
---

# NDOT status text with negations is classified as chains / closed

## Problem Statement

`ndot.classify()` matches substrings: "No Chain Controls", "Chain Controls Lifted" and "Chain controls not in effect" map to R1 (→ NO GO); "Reopened, previously closed" maps to closed; "ice" matches "device". Unknown text is treated as clear, the opposite of Caltrans' policy.

## Findings

- `backend/src/passcheck/sources/ndot.py:55-63` (probed by the Python reviewer).
- `test_ndot_classify` only has positive cases.

## Proposed Solutions

### Option 1: **Negation-first, word-boundary classifier.** Check "no chain", "lifted", "not in effect", "reopen" first; use `\b` regexes; unknown non-empty text → CAUTION (same policy as Caltrans). Effort: Small. Risk: Low.

### Option 2: **Allowlist of known nvroads phrases** with everything else → CAUTION. Effort: Small. Risk: Medium (unknown phrases).

## Recommended Action

Option 1 implemented. `ndot.classify` normalises whitespace, strips negation phrases first ("no chain(s)/restrictions/closures/delays", "chain controls [have been] lifted/removed/cancelled/not in effect/not required", "reopen(ed|s|ing)", "previously closed", bare "lifted"/"not in effect"), then matches hazards on `\b` word boundaries in order closed > R-code (R1-R3) > chains required (R2) > chains/traction/snow tires (R1) > holding/snow/ice/icy/slick/slush (CAUTION). Remaining text is clear only if a negation matched or it contains dry/clear/normal/open/good; empty text is clear; anything else is CAUTION, matching Caltrans.

## Technical Details

**Affected files:** backend/src/passcheck/sources/ndot.py, backend/tests/test_merge_and_sources.py

## Acceptance Criteria

- [x] Negated/lifted/reopened strings classify as clear.
- [x] Word boundaries (device ≠ ice).
- [x] Unknown text → CAUTION; tests cover all of these.

## Work Log

### 2026-11-15 - Code review of PR #1
- Found by the /workflows:review agents on branch feat/pass-check-app.

### 2026-11-15 - Resolved (backend sources/corridors/security)
- Rewrote classify in backend/src/passcheck/sources/ndot.py; expanded test_ndot_classify to 27 cases (positives, negations, all-clear, device≠ice, negation-plus-hazard, unknown→CAUTION).
- `uv run pytest tests/test_merge_and_sources.py tests/test_scheduler.py` passes; ruff + pyright strict clean on touched files.

## Resources

- PR: https://github.com/treasonx/reno_route_planner/pull/1
