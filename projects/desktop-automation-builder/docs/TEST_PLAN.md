# Test plan — Desktop Automation Builder

**Current test status:** RUN 2026-10-23 (Linux VM, Node 24, Electron 45, Vitest 5.0.5) — **44/44 pass** across 8 files:
`tests/backend/*` (29 — dry-run performs zero writes; sandbox escape `../evil` and absolute-outside paths rejected with `PATH_OUTSIDE_SANDBOX`; `runsStart(approved=false)` → `awaiting-approval` with no side effects; mid-run failure persists partial log, retry resumes from the failed step only and retrying a non-failed run throws `RUN_NOT_RETRYABLE`; cancel mid-run → `cancelled` + persisted partial log; unapproved scriptId blocked; move-to-trash lands in `.dab-trash/` fully recoverable; version bumps archive snapshots; export `formatVersion 1.0.0` / import rejects major ≠ 1 and bad shapes; preload channel map asserted 1:1),
`tests/renderer/*` (15 — hermetic mocked `window.dab`: editor add/remove/reorder + per-kind fields, import validation errors surface, approval gating incl. preview-before-start ordering and `runsStart` called with `true` only after the checkbox, run-log outcomes, retry shown only on failed runs, cancel, delete confirmation).
`npm run typecheck` clean, `npm run lint` clean, `npm run build` green, `npm run smoke` PASS (packaged main prints SMOKE_OK under Xvfb). Re-verified independently by the coordinator on the final pushed tree (fresh `npm ci`).
Windows click-through not executed here — marked pending, not passing.

## Required automated and integration scenarios

- Dry-run performs no writes
- Filesystem scope and path traversal rejection
- Cancelled runs record recoverable state
- Approval required for dangerous actions
- Untrusted workflow imports do not execute automatically

## Cross-cutting tests

- Validate malformed, missing, oversized and unauthorized inputs.
- Confirm persistence, restart behavior, schema versioning, and export/import consistency where relevant.
- Exercise cancellation, timeouts, incomplete operations and recovery behavior.
- Confirm tests use temporary fixtures and do not read owner's private or production data.
- Verify deterministic calculations and no accidental state changes in read-only actions.

## End-to-end MVP verification

Build a simple non-destructive file-copy workflow, preview its actions, approve, run, inspect log, and retry safely.

Run this workflow against a real application build using disposable data; record actual commands, OS environment, relevant results and any platform-only gaps. If the workflow requires Windows or local AI services unavailable in the worker environment, mark it **implemented but unverified** rather than passing.

## Mandatory verification record

For each run, capture: commit SHA, command, execution environment, passed/failed/skipped counts, observed UI/CLI behavior, defect links, and next action. Keep logs free of credentials and personal data.

No release or owner-acceptance claim before end-to-end demonstration.
