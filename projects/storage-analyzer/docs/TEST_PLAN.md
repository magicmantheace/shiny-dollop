# Test plan — PC Storage and Duplicate Finder

**Current test status:** NOT RUN. This document defines future acceptance; no test results are implied.

## Required automated and integration scenarios

- Identical and same-size-different-content fixture files
- Symlink/junction loops and inaccessible folders
- Cancellation and partial-result labeling
- File changes while hashing
- No file writes or deletion during scanning

## Cross-cutting tests

- Validate malformed, missing, oversized and unauthorized inputs.
- Confirm persistence, restart behavior, schema versioning, and export/import consistency where relevant.
- Exercise cancellation, timeouts, incomplete operations and recovery behavior.
- Confirm tests use temporary fixtures and do not read owner's private or production data.
- Verify deterministic calculations and no accidental state changes in read-only actions.

## End-to-end MVP verification

Choose a directory, view ranked file/folder sizes and verified duplicate groups, cancel scans, and export a report; no deletion.

Run this workflow against a real application build using disposable data; record actual commands, OS environment, relevant results and any platform-only gaps. If the workflow requires Windows or local AI services unavailable in the worker environment, mark it **implemented but unverified** rather than passing.

## Mandatory verification record

For each run, capture: commit SHA, command, execution environment, passed/failed/skipped counts, observed UI/CLI behavior, defect links, and next action. Keep logs free of credentials and personal data.

No release or owner-acceptance claim before end-to-end demonstration.

---

## Appendix — Automated test record (Worker B renderer, 2026-10-23)

Environment: Linux VM, Node v24.22.1, `projects/storage-analyzer/app`.
Renderer tests mock `window.storageAnalyzer` (see `src/__tests__/mockStorageAnalyzer.ts`);
no real filesystem or Electron APIs are touched.

| Command | Result |
|---|---|
| `npx vitest run --project ui` | **35/35 passed** (6 files: App, StartView, ScanView, ResultsView, HistoryView, format) |
| `npx tsc --noEmit -p tsconfig.renderer.json` | green |
| `npx eslint src/` | green |
| `npm run build:renderer` (vite) | green, `dist/renderer/` emitted |

UI test coverage maps to the required scenarios: start-scan flow (choose folder →
edit exclusions → `scan.start` called with parsed exclusions); cancel button calls
`scan.cancel` and shows the terminal state; live progress renders files/dirs/bytes
and current path from `scan.progress` events (events for other scanIds ignored);
`scan.finished` resolves the authoritative status; stale label appears for
incomplete scans and when a newer scan of the same root exists (and is absent
otherwise); duplicate groups render SHA-256, file list and `size×(n−1)` savings;
search submits the query and renders filtered hits; CSV and JSON export invoke
`export.report` with `{ scanId, format, outPath }`; backend envelope errors surface
as a dismissible banner with actionable text.

Full-suite run (`npx vitest run`) also executes Worker A's backend project:
12 tests, **1 failing** — `tests/shared/contract.test.ts` › "matches substrings
case-insensitively" (backend `isExcluded` does not match `a/NODE_MODULES/...`
against pattern `node_modules`). Backend-owned; not a renderer issue.

**Not executed:** real Electron window launch, live end-to-end scan, Windows-only
behaviors, NSIS/portable-zip packaging (no Wine on this VM). These are recorded
as unverified, not passing.
