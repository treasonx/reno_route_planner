---
status: complete
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

Option 1. Split `.github/workflows/docker-publish.yml` into a read-only `scan` job (contents: read; amd64 load build + Trivy CRITICAL/ignore-unfixed/exit-code 1; runs on every event including pull_request) and a `publish` job (`needs: scan`, `if: github.event_name != 'pull_request'`, contents: read + packages: write) that pushes amd64+arm64 and then Trivy-scans the pushed digest (`${{ env.IMAGE }}@${{ steps.push.outputs.digest }}`) per platform via `TRIVY_PLATFORM=linux/amd64` and `linux/arm64`.

## Technical Details

**Affected files:** .github/workflows/docker-publish.yml

## Acceptance Criteria

- [x] PR runs have no package write permission.
- [x] Published platforms are scanned.

## Work Log

### 2026-11-15 - Code review of PR #1
- Found by the /workflows:review agents on branch feat/pass-check-app.

### 2026-11-15 - Resolved
- Split workflow into `scan` (contents: read, all events) and `publish` (needs scan, non-PR only, packages: write).
- Publish job scans the pushed image by digest for linux/amd64 and linux/arm64 (fails on fixable criticals).
- Top-level `permissions: {}` and `persist-credentials: false` kept; all actions remain pinned to the same commit SHAs.
- YAML validated with PyYAML.

## Resources

- PR: https://github.com/treasonx/reno_route_planner/pull/1
