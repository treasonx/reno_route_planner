---
status: pending
priority: p2
issue_id: "002"
tags: [code-review, architecture, reliability]
dependencies: []
---

# Plan response cache is not thread-safe

## Problem Statement

`api.plan` is a sync `def`, so FastAPI runs it in a threadpool, while `Store._rebuild` clears the `OrderedDict` cache on the event-loop thread. `Store.cached` does `get` then `move_to_end`; an interleaved clear/evict raises `KeyError` → 500.

## Findings

- `backend/src/passcheck/api.py:70` sync handler.
- `backend/src/passcheck/store.py:101,122-125` unsynchronised OrderedDict.

## Proposed Solutions

### Option 1: **Make the handler `async def`.** All store access happens on the loop thread; plan building is ~26 ms. Effort: Small. Risk: Low.

### Option 2: **Add a `threading.Lock`** around cached/put/clear. Effort: Small. Risk: Low.

## Recommended Action

_(Filled during triage.)_

## Technical Details

**Affected files:** backend/src/passcheck/api.py, backend/src/passcheck/store.py

## Acceptance Criteria

- [ ] No shared-mutable access to the cache from more than one thread.
- [ ] Tests still pass.

## Work Log

### 2026-11-15 - Code review of PR #1
- Found by the /workflows:review agents on branch feat/pass-check-app.

## Resources

- PR: https://github.com/treasonx/reno_route_planner/pull/1
- Plan: docs/plans/2026-11-15-feat-pass-check-app-and-docker-image-plan.md
