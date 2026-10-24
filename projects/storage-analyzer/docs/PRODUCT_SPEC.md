# Product specification — PC Storage and Duplicate Finder

**Intake status:** Approved project concept; implementation not started.
**Priority:** 4/17
**Audience/target platform:** Windows utility

## Problem and outcome

Understand drive usage and duplicate files with non-destructive analysis and transparent evidence.

## MVP user workflow and acceptance contract

Choose a directory, view ranked file/folder sizes and verified duplicate groups, cancel scans, and export a report; no deletion.

The MVP is accepted only when a tester can complete the workflow using an actual running build, inspect the resulting data/artifact, restart when relevant, and reproduce the result. Showing an interface or a unit test alone is not an MVP.

## Requirements — initial and subsequent milestones

1. **Folder and drive-space treemap/list** — implement with persisted, validated state and meaningful user feedback where relevant.
2. **Large-file filtering** — implement with persisted, validated state and meaningful user feedback where relevant.
3. **Size-first and hash-confirmed duplicate groups** — implement with persisted, validated state and meaningful user feedback where relevant.
4. **Search and file-type summaries** — implement with persisted, validated state and meaningful user feedback where relevant.
5. **Exclusion rules and protected-path warnings** — implement with persisted, validated state and meaningful user feedback where relevant.
6. **Cancellable scans with progress** — implement with persisted, validated state and meaningful user feedback where relevant.
7. **CSV/JSON results and rescan comparison** — implement with persisted, validated state and meaningful user feedback where relevant.

## Data model and architecture considerations

Windows desktop UI plus cancellable background filesystem indexer and SHA-256 duplicate verification.

Use a clearly versioned and documented local storage/export format. Define entities and transitions from the MVP workflow, not guessed integrations. Include migration and backup/restore behavior before treating persisted data as production-ready.

## Integration strategy

Standalone.

No other application's source or database may be modified as part of this project. Where useful, exchange versioned export/import contracts and independently owned fixtures.

## Nonfunctional and safety requirements

Initial MVP is read-only. Never follow reparse points into loops; no system-directory modifications; clearly label stale results.

- Prefer offline operation and no paid API dependency.
- Optimize for a Windows 11 desktop (i5-10400F, RTX 3060 12 GB, 32 GB RAM), where relevant.
- Avoid destructive defaults, unapproved network calls, or hidden data collection.
- Make errors actionable; provide accessible keyboard navigation and recovery paths.
- Use original/licensed assets and scrub private example data.

## Completion criteria

1. Runnable build and reproducible install or launch instructions.
2. End-to-end MVP workflow exercised with recorded evidence.
3. Focused automated tests and relevant platform manual tests executed.
4. Clear distinction between implemented, verified, planned and blocked features.
5. Scoped pull request left unmerged for review.

---

## Appendix — As-built behavior (2026-10-23, Worker B renderer)

What the React renderer (`app/src/`) actually implements, against the canonical
`app/shared/` IPC contract (Worker A's backend):

- **Start view** (`views/StartView.tsx`): native folder dialog via
  `dialog.chooseDirectory()`; exclusion editor, one pattern per line, parsed and
  deduped by `parseExclusions()`; defaults `node_modules`, `$RECYCLE.BIN`,
  `System Volume Information`; client-side protected-path heuristic
  (`isProtectedPath()`: drive roots and Windows system folder segments) shows a
  warning banner; Start calls `scan.start({ rootPath, exclusions })` and forwards
  the backend's `warning` (`'protected-path'`) to the scan view.
- **Scan view** (`views/ScanView.tsx`): subscribes to `scan.progress` /
  `scan.finished` and polls `scan.status` every 2 s; shows files / folders / bytes,
  current path, indeterminate progress bar, `aria-live="polite"` status; Cancel
  calls `scan.cancel()`; terminal states reveal "View results" / "New scan";
  skipped-entry and mid-scan-changed-file counters shown when nonzero; backend
  `error` string rendered with `role="alert"`.
- **Results view** (`views/ResultsView.tsx`): loads `results.summary()`,
  `results.duplicates()` and `scan.list()` in parallel; scan timestamp plus a
  **stale** label when the scan state isn't `complete` or a newer scan of the same
  root exists; folder sizes top 20, largest files top 50, full type-summary table;
  duplicate groups show size × copies, full SHA-256, file list, and potential
  savings `size × (n−1)` — informational only, **no delete affordance anywhere**;
  search box calls `results.search()` and renders up to 500 hits with an
  `aria-live` count; export row takes an output path and calls
  `export.report({ scanId, format, outPath })` for `csv` and `json`.
- **History view** (`views/HistoryView.tsx`): `scan.list()` rendered newest-first
  with state badges; each row is a button opening that scan's results.
- **Error handling** (`api.ts`): the `{ ok, data } / { ok, error }` envelope is
  unwrapped into a typed `IpcError`; known backend codes (`SCAN_NOT_FOUND`,
  `PATH_NOT_FOUND`, `ACCESS_DENIED`, `EXPORT_FAILED`, `NO_BRIDGE`) map to
  actionable messages shown in a dismissible `role="alert"` banner.
- **Not built (per MVP scope):** treemap visualization, large-file filtering,
  rescan comparison, cleanup preview / deletion, scheduled scans.
