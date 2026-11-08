# PC Storage and Duplicate Finder

**Status:** MVP functional / review ready (renderer complete and verified; backend landed on the same branch — see Verification).

**Priority:** 4 of 17 in the approved intake queue.
**Category:** Windows utility
**Repository workspace:** `projects/storage-analyzer/`

## Purpose

Understand drive usage and duplicate files with non-destructive analysis and transparent evidence.

## First usable release (MVP)

Choose a directory, view ranked file/folder sizes and verified duplicate groups, cancel scans, and export a report; no deletion.

## Features (as built)

- **Start view** — native folder picker, editable exclusion patterns (defaults: `node_modules`, `$RECYCLE.BIN`, `System Volume Information`), and a protected-path warning banner for drive roots / Windows system folders.
- **Scan view** — live progress (files, folders, bytes, current path) via `scan.progress` events plus status polling, indeterminate progress bar, Cancel button, skipped-entry and mid-scan-change counters, and the backend's protected-path warning when returned by `scan.start`.
- **Results view** — scan timestamp with a **stale label** when the scan didn't complete or a newer scan of the same root exists; ranked folder sizes (top 20), largest files (top 50), file-type summary table, SHA-256 duplicate groups with per-group file list and potential savings (`size × (copies − 1)`); full-text search (max 500 hits); CSV/JSON export to a user-supplied output path.
- **History view** — past scans with state badges (running / complete / cancelled / failed), newest first; click to open results.
- Read-only throughout: **no deletion UI exists** and none is planned for the MVP. Duplicates are informational only.
- Accessible labels on all inputs; `aria-live` regions for scan status and search results; actionable error messages via the typed IPC error envelope.

## Quick start

```bash
cd projects/storage-analyzer/app
npm install
npm run dev        # renderer dev server (needs Worker A's main-process wiring for full app)
```

The app is an Electron app: the React renderer (`app/src/`, Worker B) talks to the
main process (`app/electron/`, Worker A) through the typed `window.storageAnalyzer`
bridge defined in `app/shared/api-types.ts`. Renderer types re-export the canonical
`app/shared/` contract — no duplicate declarations.

## Tests

```bash
cd projects/storage-analyzer/app
npx vitest run --project ui   # 35 UI tests (mocked window.storageAnalyzer)
npx vitest run                # UI + backend suites
npm run typecheck              # main + preload + renderer
npx eslint .
npm run build:renderer         # vite production build of the renderer
```

UI tests render against a mocked `window.storageAnalyzer` and cover: start-scan flow,
cancel behavior, live progress rendering, stale labeling, duplicate-group display with
savings math, search filtering, CSV/JSON export invocation, and error display.

## Verification

Evidence recorded 2026-10-23 (Linux VM, Node 24):

- `npx vitest run --project ui` — **35/35 passed** (6 files).
- `npx tsc --noEmit -p tsconfig.renderer.json` — green.
- `npx eslint src/` — green.
- `npm run build:renderer` — green (`dist/renderer/`).
- Backend (Worker A, same branch): 12 tests, **1 failing** (`tests/shared/contract.test.ts`
  "matches substrings case-insensitively"); `tsc` on the main project reports
  **1 error** (`electron/main/db/scans.ts` TS2352 cast); `npx eslint .` reports
  **2 unused-variable errors** in backend files. These are Worker A's to resolve;
  full `npm run typecheck` / `npx eslint .` are not green until then.

## Unfinished

- Real Electron window launch and end-to-end scan against a live backend — not run on
  this Linux VM (needs Windows for a faithful run).
- Portable Windows zip / NSIS installer assembly — configured in `electron-builder.yml`
  but not built here (no Wine); see `docs/WINDOWS_INSTALL.md` for the Windows-side steps.
- Backend fixes listed under Verification above (Worker A).
- No PR opened yet — branch `storage-analyzer/mvp` is the review vehicle.

## Full intended capabilities

- Folder and drive-space treemap/list
- Large-file filtering
- Size-first and hash-confirmed duplicate groups
- Search and file-type summaries
- Exclusion rules and protected-path warnings
- Cancellable scans with progress
- CSV/JSON results and rescan comparison

## Dependencies and boundaries

Standalone.

Initial MVP is read-only. Never follow reparse points into loops; no system-directory modifications; clearly label stale results.

## Muse start point

Read the repository-root `AGENTS.md`, then [this project's instructions](AGENTS.md) and [development handoff](docs/MUSE_HANDOFF.md). Implement the smallest working end-to-end milestone; document genuine test results. See [specification](docs/PRODUCT_SPEC.md), [test plan](docs/TEST_PLAN.md), and [status](docs/IMPLEMENTATION_STATUS.md).
