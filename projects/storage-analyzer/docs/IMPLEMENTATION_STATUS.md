# Implementation status — PC Storage and Duplicate Finder

- **Overall status:** MVP functional / review ready (renderer + backend verified on Linux; Windows end-to-end pending)
- **Priority:** 4/17
- **Branch:** `storage-analyzer/mvp`
- **Source/code implemented:** React 19 renderer (`app/src/`, Worker B) + Electron backend,
  shared IPC contract, configs and backend tests (`app/electron/`, `app/shared/`,
  `app/tests/`, Worker A) — both halves on the same branch
- **Build validated:** `npm run typecheck` (main+preload+renderer), `npm run lint`, `npm run build`, and `npm run smoke` (real window under xvfb, SMOKE_OK) all green on Linux 2026-10-23 — independently re-verified by coordinator on the final pushed tree
- **Automated tests executed:** yes — 35/35 UI tests pass; 42/42 backend tests pass
- **End-to-end MVP verified:** No — needs a Windows run against the live backend
- **Owner review:** Pending

## First milestone

Choose a directory, view ranked file/folder sizes and verified duplicate groups, cancel scans, and export a report; no deletion.

## Verified (2026-10-23, Linux VM, Node 24)

- `npx vitest run --project ui` — 35/35 passed (start flow, cancel, progress,
  stale labeling, duplicate display + savings math, search, export, error display).
- `npx tsc --noEmit -p tsconfig.renderer.json` — green.
- `npx eslint src/` — green.
- `npm run build:renderer` — green.
- Renderer imports its IPC types from the canonical `app/shared/` contract; the
  preload's `window.storageAnalyzer` surface (`onProgress`/`onFinished` included)
  matches the renderer's typed bridge exactly.

## Verified — backend (2026-10-23, Linux VM, Node 24, Worker A)

- `npx vitest run --project backend` — 42/42 passed: duplicate confirmation,
  same-size-different-content rejection, symlink-loop termination, EACCES
  recording, mid-scan cancel with partial results, changed-during-scan skip
  (no false groups), zero-writes-to-tree, exclusions, export CSV/JSON, schema
  validation, protected-path detection.
- `npx tsc --noEmit -p tsconfig.main.json` and `tsconfig.preload.json` — green.
- `npx eslint .` — green.
- `npm run build:main`, `build:preload`, `build:renderer` — all green.
- Production bundle opens a real native window under xvfb (`SMOKE_OK`).
- Earlier "Pending (backend)" items are resolved: the exclusion test failure was
  a test bug (un-normalized input), the scans.ts TS2352 cast was reworked, and
  the eslint unused-variable errors were removed.

## Codex fix cycle 1 (2026-10-24, Linux VM, Node 24)

- Hash candidates are revalidated after reading (identity, size, mtime, ctime
  vs the pre-read stat): a file changed during its own hash stream is now
  excluded and counted as changed instead of forming a "verified" duplicate
  group from stale bytes. Two regression tests (append-during-read and
  same-size in-place rewrite) fail without the revalidation.
- Quit during a scan now settles scan jobs before the database closes
  (`settleAllScans`, bounded), and scans left in `running` state are
  reconciled to `failed` ("Interrupted…") on startup and after settling
  (`markRunningScansInterrupted`) instead of appearing to run forever.
  Covered by `tests/ipc/shutdown.test.ts` + a reconciliation test in
  `tests/db/scans.test.ts`.
- Full suite after the fixes: 83/83 tests pass (11 files); `npm run typecheck`
  and `npm run lint` green.

## Codex fix cycle 2 (2026-10-24, Linux VM, Node 24)

- Hard-link aliases no longer inflate duplicate savings: file records now
  store their (dev, ino) identity (migration v2), the scanner retains that
  identity on hash candidates and never hashes a second path to an inode
  already in the size group, and `getDuplicateGroups` collapses aliases by
  identity — a group needs ≥2 distinct inodes, and savings are
  size × (distinct files − 1). Regression tests: 2 engine tests with real
  `fs.link` fixtures (two links to a 4-byte file form no group; alias +
  independent copy counts once) + 2 DB-level identity tests; all failed
  before the fix.
- File search normalizes Unicode consistently on both sides: a stored
  `path_search` key (NFC + `toLowerCase()`, backfilled for pre-v2 rows by
  `runMigrations`) is matched against a query normalized by the same
  `normalizeForSearch` helper, replacing the JS-vs-SQLite `lower()`
  mismatch that missed names like `ÉTÉ.txt`. Regression tests cover
  non-ASCII case folding, decomposed vs precomposed forms, and a v1→v2
  upgrade with backfill.
- Full suite after the fixes: 90/90 tests pass (11 files, +7 new);
  `npm run typecheck` and `npm run lint` green.

## Pending (platform)

- Real Electron window launch + live end-to-end scan on Windows (unverified here).
- Portable zip / NSIS installer assembly on Windows (see `docs/WINDOWS_INSTALL.md`).

## Out of scope (MVP)

- Deletion / cleanup UI of any kind — deliberately not built; duplicates are
  informational only.
- Treemap visualization, large-file filtering, rescan comparison, scheduled scans.

## Acceptance notes

- Coordinator acceptance walkthrough (2026-10-23, Linux VM, temp harness — not committed): fixture tree with identical pdfs, same-size-different-content mkvs, and a symlink loop → scan completed; exactly 1 verified duplicate group (the 2 pdfs, mkvs correctly excluded); largest-file/type-summary correct; zero mtime changes to the scanned tree (read-only confirmed); mid-scan cancel → `cancelled` persisted; CSV + JSON exports valid. All assertions passed.
- Full gates independently re-verified by coordinator on the final pushed tree: 77/77 tests, typecheck, lint, build, smoke (`SMOKE_OK`).
- Commit(s) on `storage-analyzer/mvp`; PR left unmerged for owner review.
- Do not infer end-to-end success from the green renderer suite alone.
