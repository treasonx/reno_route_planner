---
status: complete
priority: p3
issue_id: "018"
tags: [code-review, quality, testing]
dependencies: []
---

# Inconsistent source conventions and test gaps

## Problem Statement

`assert` used for control flow (stripped by python -O); WU parses JSON in fetch; string source names vs enum; WU summits hand-listed; flaky wall-clock benchmark in default test run; frontend tests don't cover day selection, swipe/keys, or keep-last-plan-on-error.

## Findings

- caltrans.py:33, ndot.py:113, wu.py:52,68; tests/test_api.py benchmark; App.test.tsx.

## Proposed Solutions

### Option 1: **Replace asserts with explicit checks; loosen/mark benchmark; add the missing frontend tests.** Effort: Medium. Risk: Low.

### Option 2: **Only fix asserts and the flaky benchmark.** Effort: Small. Risk: Low.

## Recommended Action

Backend part of Option 1 done: no `assert` control flow left in src/passcheck/sources (caltrans._timestamp uses an explicit None check; ndot/wu fetch raise UpstreamError("not configured") without a key). WU fetch is transport-only: it returns a JSON envelope `{point_id: raw_body_text}` and parse() decodes each body (any bad body fails the whole source, like Caltrans). Remaining items (string source names vs enum, hand-listed WU summits, flaky benchmark in test_api.py, frontend tests) are outside this pass.

## Technical Details

**Affected files:** backend/src/passcheck/sources/*.py, backend/tests/test_api.py, frontend/src/App.test.tsx

## Acceptance Criteria

- [x] No assert-based control flow in src.
- [x] Benchmark not flaky; key UI flows tested.

## Work Log

### 2026-11-15 - Code review of PR #1
- Found by the /workflows:review agents on branch feat/pass-check-app.

### 2026-11-15 - Frontend resolution (partial: frontend only)
- Frontend part done in `frontend/src/App.test.tsx`: choosing a day sends `date=` and opens at 6 AM (skeleton shown meanwhile); failed refresh keeps last plan visible with the stale banner; server-stale banner; arrow keys move between route tabs and focus follows; hour selection survives an hourly refresh. Queries use accessible names robust to the 017 a11y changes (`getByLabelText(/^Mon 16/)`, `getByRole('tab', ...)`, '10-day outlook' heading). Also added hook tests for usePolling/usePlan/useSwipe.
- Backend parts (asserts in sources, WU parsing, enum names, flaky benchmark) not handled here — left pending.
- Verified: `npx tsc --noEmit && npx eslint . && npx vitest run` all pass (24 tests).

### 2026-11-15 - Resolved (backend sources/corridors/security)
- Backend source fixes in caltrans.py, ndot.py, wu.py; tests for missing-key fetch, missing Caltrans timestamp, WU envelope round trip and invalid body. Benchmark/frontend acceptance item left for the agents owning test_api.py and the frontend.
- `uv run pytest tests/test_merge_and_sources.py tests/test_scheduler.py` passes; ruff + pyright strict clean on touched files.

## Resources

- PR: https://github.com/treasonx/reno_route_planner/pull/1

### 2026-11-15 - Integration (coordinator)
- Loosened the wall-clock benchmark bound to 500 ms (local ~30 ms) so CI runners don't flake.
- WU summits now derive from corridor `peak_name` (single source of truth).
- Frontend test gaps were covered by the frontend-state resolver (day selection, keep-last-plan-on-error, tab arrow keys).
- Source names stay plain strings for non-live sources; live sources use `LiveSourceName` (accepted: names are only used as store keys).
