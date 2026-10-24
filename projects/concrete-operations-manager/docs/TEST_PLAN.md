# Test plan — Concrete Operations Manager

**Current test status:** NOT RUN. This document defines future acceptance; no test results are implied.

## Required automated and integration scenarios

- Price and tax calculations including rounding and exemptions
- Small-load threshold and alternate customer rates
- Quote revisions do not rewrite issued invoices
- Inventory receipt and consumption consistency
- Export/import recovery with synthetic customers

## Cross-cutting tests

- Validate malformed, missing, oversized and unauthorized inputs.
- Confirm persistence, restart behavior, schema versioning, and export/import consistency where relevant.
- Exercise cancellation, timeouts, incomplete operations and recovery behavior.
- Confirm tests use temporary fixtures and do not read owner's private or production data.
- Verify deterministic calculations and no accidental state changes in read-only actions.

## End-to-end MVP verification

Create a customer and job, record one pour, calculate an itemized quote with tax, finalize delivered volume, and export an invoice.

Run this workflow against a real application build using disposable data; record actual commands, OS environment, relevant results and any platform-only gaps. If the workflow requires Windows or local AI services unavailable in the worker environment, mark it **implemented but unverified** rather than passing.

## Mandatory verification record

For each run, capture: commit SHA, command, execution environment, passed/failed/skipped counts, observed UI/CLI behavior, defect links, and next action. Keep logs free of credentials and personal data.

No release or owner-acceptance claim before end-to-end demonstration.

## Execution record — 2026-10-23 (MVP)

**Environment:** Linux VM (x86_64), Node v24.22.1, Electron 45. Branch
`concrete-operations-manager/mvp` @ `9bbc6af` (foundation `104c0bd`).

| Command | Result |
|---|---|
| `npm run typecheck` (renderer, main, preload) | clean |
| `npx eslint .` | clean |
| `npx vitest run` | **57/57 pass**, 11 files, 0 failed |
| `npm run build` | production bundle built |
| `npm run smoke` | PASS — real Electron window opened (SMOKE_OK, xvfb) |
| acceptance walkthrough vs compiled `dist/` (`/tmp/com-accept-walkthrough.cjs`) | **17/17 checks pass** |

Coverage of the plan: price/tax incl. rounding & exemptions ✅; small-load
threshold & alternate customer rates ✅; quote revisions never rewrite issued
invoices ✅; inventory receipt/consumption consistency ✅; export/import recovery
with synthetic customers ✅; malformed/missing/oversized input rejection ✅;
persistence & restart ✅; schema versioning ✅; deterministic calculations ✅.

Platform gaps (marked implemented but unverified): NSIS installer build,
portable zip on Windows, real Windows file dialogs/hardware, install/uninstall.
