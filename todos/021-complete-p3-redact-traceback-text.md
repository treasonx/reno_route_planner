---
status: complete
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

Option 1 implemented. security.RedactingFormatter redacts the fully formatted output (message + traceback + stack) and scrubs the cached record.exc_text; configure_logging installs it on its handler (plus the handler-level RedactingFilter) and detects idempotency via the formatter. The ineffective root-logger filter was removed.

## Technical Details

**Affected files:** backend/src/passcheck/security.py, backend/tests/test_scheduler.py

## Acceptance Criteria

- [x] Test logs an exception containing a sentinel key; output is redacted.

## Work Log

### 2026-11-15 - Code review of PR #1
- Found by the /workflows:review agents on branch feat/pass-check-app.

### 2026-11-15 - Resolved (backend sources/corridors/security)
- Added RedactingFormatter and updated configure_logging in security.py; added test_exception_traceback_is_redacted in test_scheduler.py (log.exception with a sentinel apiKey in the exception message; asserts redaction, single handler, no root filter).
- `uv run pytest tests/test_merge_and_sources.py tests/test_scheduler.py` passes; ruff + pyright strict clean on touched files.

## Resources

- PR: https://github.com/treasonx/reno_route_planner/pull/1
