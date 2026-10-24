# Test plan — Household Inventory and Warranty Tracker

**Current test status:** RUN 2026-10-23 (Linux VM, Node 24) — **59/59 pass** across 10 files:
`tests/engine/*` (warranty date math incl. leap-day 2024-02-29 accepted / 2023-02-29 rejected, today/tomorrow/yesterday boundaries, null end → 'none'),
`tests/db/*` (CRUD round-trip, attachment sha256 integrity + missing-file tolerance + cascade file cleanup on item delete,
backup export→import round-trip with byte-identical attachments, tamper rejection on sha256 mismatch / missing file / garbage zip / wrong manifest / zip-slip path),
`tests/ui/*` (hermetic `window.inv` mocks: search/category filtering, expired-vs-expiring sections + empty state, form validation incl. dollars→cents, oversized-file warning + upload block),
`tests/integration/acceptance.test.ts` (full MVP walkthrough: 2 items + receipt + maintenance event + warranty finder + backup round-trip into a fresh dir).
`npm run typecheck` clean, `npm run lint` clean, `npm run build` green, `npm run smoke` PASS (real window, SMOKE_OK).
Windows click-through not executed here — marked pending, not passing.

## Required automated and integration scenarios

- Item CRUD and attachment integrity
- Warranty expiration across date boundaries
- Backup export/import round trip
- Missing attachment and duplicate serial number handling
- No private record appears in repository/logs

## Cross-cutting tests

- Validate malformed, missing, oversized and unauthorized inputs.
- Confirm persistence, restart behavior, schema versioning, and export/import consistency where relevant.
- Exercise cancellation, timeouts, incomplete operations and recovery behavior.
- Confirm tests use temporary fixtures and do not read owner's private or production data.
- Verify deterministic calculations and no accidental state changes in read-only actions.

## End-to-end MVP verification

Add an item and receipt, record purchase and warranty dates, find expiring warranties, and export a backup.

Run this workflow against a real application build using disposable data; record actual commands, OS environment, relevant results and any platform-only gaps. If the workflow requires Windows or local AI services unavailable in the worker environment, mark it **implemented but unverified** rather than passing.

## Mandatory verification record

For each run, capture: commit SHA, command, execution environment, passed/failed/skipped counts, observed UI/CLI behavior, defect links, and next action. Keep logs free of credentials and personal data.

No release or owner-acceptance claim before end-to-end demonstration.
