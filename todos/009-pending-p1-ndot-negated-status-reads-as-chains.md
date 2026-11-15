---
status: pending
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

_(Filled during triage.)_

## Technical Details

**Affected files:** backend/src/passcheck/sources/ndot.py, backend/tests/test_merge_and_sources.py

## Acceptance Criteria

- [ ] Negated/lifted/reopened strings classify as clear.
- [ ] Word boundaries (device ≠ ice).
- [ ] Unknown text → CAUTION; tests cover all of these.

## Work Log

### 2026-11-15 - Code review of PR #1
- Found by the /workflows:review agents on branch feat/pass-check-app.

## Resources

- PR: https://github.com/treasonx/reno_route_planner/pull/1
