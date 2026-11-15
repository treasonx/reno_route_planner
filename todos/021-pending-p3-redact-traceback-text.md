---
status: pending
priority: p3
issue_id: "021"
tags: [code-review, security, logging]
dependencies: []
---

# Log redaction does not cover exception tracebacks

## Problem Statement

`RedactingFilter` rewrites `record.msg` only; text added by `formatException` is not redacted. No code logs exceptions today, but a future `log.exception` could leak a key in a URL.

## Findings

- `backend/src/passcheck/security.py`.

## Proposed Solutions

### Option 1: **Redacting Formatter** that redacts the fully formatted output. Effort: Small. Risk: Low.

### Option 2: **Lint rule banning log.exception in sources.** Effort: Small. Risk: Medium.

## Recommended Action

_(Filled during triage.)_

## Technical Details

**Affected files:** backend/src/passcheck/security.py, backend/tests/test_scheduler.py

## Acceptance Criteria

- [ ] Test logs an exception containing a sentinel key; output is redacted.

## Work Log

### 2026-11-15 - Code review of PR #1
- Found by the /workflows:review agents on branch feat/pass-check-app.

## Resources

- PR: https://github.com/treasonx/reno_route_planner/pull/1
