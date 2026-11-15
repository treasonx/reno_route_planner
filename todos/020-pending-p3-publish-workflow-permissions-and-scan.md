---
status: pending
priority: p3
issue_id: "020"
tags: [code-review, security, ci]
dependencies: []
---

# PR runs get packages:write; pushed image differs from scanned image

## Problem Statement

The single job grants `packages: write` on pull_request runs; Trivy scans a separate amd64 load build while the pushed multi-arch image is built again (arm64 never scanned).

## Findings

- `.github/workflows/docker-publish.yml`.

## Proposed Solutions

### Option 1: **Split into a read-only scan job and a publish job** (non-PR only) with packages:write; scan the pushed digest per platform. Effort: Small. Risk: Low.

### Option 2: **Only split permissions.** Effort: Small. Risk: Low.

## Recommended Action

_(Filled during triage.)_

## Technical Details

**Affected files:** .github/workflows/docker-publish.yml

## Acceptance Criteria

- [ ] PR runs have no package write permission.
- [ ] Published platforms are scanned.

## Work Log

### 2026-11-15 - Code review of PR #1
- Found by the /workflows:review agents on branch feat/pass-check-app.

## Resources

- PR: https://github.com/treasonx/reno_route_planner/pull/1
