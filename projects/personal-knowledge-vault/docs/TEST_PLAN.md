# Test plan — Personal Knowledge Vault

**Current test status:** NOT RUN. This document defines future acceptance; no test results are implied.

## Required automated and integration scenarios

- Candidate data never silently becomes verified
- Revision history is immutable/auditable
- Search and source references survive restore
- Nonexistent source handling
- No private records sent to remote services

## Cross-cutting tests

- Validate malformed, missing, oversized and unauthorized inputs.
- Confirm persistence, restart behavior, schema versioning, and export/import consistency where relevant.
- Exercise cancellation, timeouts, incomplete operations and recovery behavior.
- Confirm tests use temporary fixtures and do not read owner's private or production data.
- Verify deterministic calculations and no accidental state changes in read-only actions.

## End-to-end MVP verification

Create unverified notes with sources, approve individual records, search them, correct history, and export a safe backup.

Run this workflow against a real application build using disposable data; record actual commands, OS environment, relevant results and any platform-only gaps. If the workflow requires Windows or local AI services unavailable in the worker environment, mark it **implemented but unverified** rather than passing.

## Mandatory verification record

For each run, capture: commit SHA, command, execution environment, passed/failed/skipped counts, observed UI/CLI behavior, defect links, and next action. Keep logs free of credentials and personal data.

No release or owner-acceptance claim before end-to-end demonstration.

## Verification record — backend MVP (Worker A)

- **Commit:** `3fef7eadbd8156b29930af2a7d2de9c275d497f2`
- **Date:** 2026-10-23 (~15:45 MDT)
- **Environment:** Linux VM, Node v24.22.1, npm 10.9.4, SQLite via node:sqlite
  (FTS5 compile option confirmed = 1). All tests use in-memory SQLite with
  synthetic fixtures; no owner data.
- **Commands and results:**
  - `npm test` (vitest, `tests/backend/`) — 6 files, **38 passed, 0 failed**.
  - `npm run typecheck` (tsc, main + preload configs) — clean.
  - `npm run lint` (eslint, backend scope) — clean.
  - `npm run build` (tsc main + preload → `dist/`) — clean.
  - `npm run smoke` (compiled `dist/` against in-memory DB: migrations,
    create→approve→search→revise→export→import) — all checks pass.
- **Coverage of required scenarios:**
  - Full workflow create→approve→search→revise→export→import round-trip ✅
  - Candidate data never silently becomes verified (approve only from
    candidate; isolation test proves note B untouched) ✅
  - Revision history immutable/auditable (DB-level trigger rejects direct
    UPDATE; rev_no monotonic per note) ✅
  - Reject without reason blocked (`REJECT_REASON_REQUIRED`) ✅
  - FTS index stays in sync on edit and delete; hostile query syntax
    (quotes/OR/wildcards) cannot break search ✅
  - Corrupt JSON / unknown major version / schema violations rejected with
    named errors (`BACKUP_CORRUPT`, `BACKUP_VERSION_UNSUPPORTED`,
    `BACKUP_IMPORT_INVALID`); export is byte-deterministic ✅
  - Self-links and missing link targets rejected ✅
  - Search and source references survive restore ✅
- **Not covered here (out of backend scope):** renderer UI behaviour, the
  Electron save-dialog path in `backup.export` (headless environment),
  Windows packaging (`electron-builder --win`), and real-window IPC
  round-trips. Renderer tests (`tests/ui/`) are Worker B's; at the time of
  this run 29 of their in-flight UI tests fail — owned by Worker B.
- **Next action:** Worker B wires `app/src/` against the `window.pkv`
  contract (`app/shared/types.ts` is the single source of truth); then a
  real packaged build on Windows for end-to-end MVP verification.

## Coordinator verification run — 2026-10-23 (Linux VM, Node 24)

- Reconciliation fixes: 7 renderer type errors repaired (View-union narrowing
  in App.tsx, `exactOptionalPropertyTypes` on SourceLabel props ×3, diff.ts
  index guards, global Window.pkv declaration); gates rewired so `npm run
  typecheck` covers main + preload + renderer, `npm test` runs all suites,
  `npm run build` includes the renderer.
- `npm test`: **69/69 pass** (38 backend + 31 UI, 11 files)
- `npm run typecheck`: clean (3 configs) · `npm run lint`: clean ·
  `npm run build`: green (main + preload + renderer bundle) ·
  `npm run smoke`: PASS (backend checks against compiled dist)
- MVP acceptance (backend workflow test, real engine, synthetic fixtures):
  create 2 candidate notes with sources + link → approve one (other provably
  untouched) → FTS search finds both → revise with change summary (revision
  row appended, immutable) → export versioned backup → import into fresh DB
  restores notes/sources/revisions/statuses identically.
- Honestly pending: real-window UI flow, Electron save-dialog path, Windows
  packaging (`package:win`), all on the owner's Windows 11 hardware.
