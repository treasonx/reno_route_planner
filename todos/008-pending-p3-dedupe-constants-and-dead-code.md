---
status: pending
priority: p3
issue_id: "008"
tags: [code-review, quality, simplicity]
dependencies: []
---

# Duplicated constants, dead fields and a redundant 404 path

## Problem Statement

Small cleanup from the simplicity and architecture reviews: constants are defined twice and can drift; some fields are never read.

## Findings

- `api.py` DAYS_AHEAD / FORECAST_MAX_AGE duplicate planner/domain constants (status vs plan staleness can drift).
- Two /api 404 catch-alls (api.py and main.py spa).
- Unused: `LiveResult.source`, `UpstreamError.source`, `app.state.settings`.
- `security.py` adds RedactingFilter to the root logger and its handler (root filter is redundant).
- `DayPlan.best_route` typed Optional but always set.
- Unreachable `if (!hour)` branch in App.tsx.

## Proposed Solutions

### Option 1: **Apply the listed cleanups** (~50 LOC). Effort: Small. Risk: Low.

### Option 2: **Only dedupe the constants** (the drift risk). Effort: Small. Risk: Low.

## Recommended Action

_(Filled during triage.)_

## Technical Details

**Affected files:** backend/src/passcheck/api.py, store.py, security.py, planner.py, schemas.py, sources/base.py, frontend/src/App.tsx

## Acceptance Criteria

- [ ] One definition each for day horizon and staleness windows.
- [ ] Lint, pyright, tests pass.

## Work Log

### 2026-11-15 - Code review of PR #1
- Found by the /workflows:review agents on branch feat/pass-check-app.

## Resources

- PR: https://github.com/treasonx/reno_route_planner/pull/1
- Plan: docs/plans/2026-11-15-feat-pass-check-app-and-docker-image-plan.md
