# Implementation status — Universal Game Save Manager

- **Overall status:** MVP functional / review ready (2026-10-23)
- **Priority:** 1/17
- **Source/code implemented:** Full MVP in `projects/game-save-manager/app/` (Electron 45 + React 19 + TypeScript strict + Vite, `node:sqlite`, zod-validated IPC)
- **Build validated:** Yes — `npm run typecheck`, `lint`, `build`, `smoke` all green on Linux (2026-10-23), independently re-run by reviewer
- **Automated tests executed:** Yes — **88/88 pass** (62 backend with real fs fixtures + 26 UI), 2026-10-24
- **End-to-end MVP verified:** Yes on Linux via automated tests on real fixtures (backup → modify → restore → byte-identical recovery); **pending on real Windows hardware** per the test plan's platform-gating rule
- **Owner review:** Pending — PR shiny-dollop #4 open and unmerged

## Codex-review fixes (2026-10-23, on `game-save-manager/initial-development`)

All five findings from the Codex review of PR #4 were verified real and fixed:

1. **manifest.json collision (data loss):** backup metadata moved from `<backupDir>/manifest.json` (inside the mirrored tree) to a sibling `<backupDir>.manifest.json`. Reads check the sibling first, fall back to the legacy in-tree path — old backups still verify/restore. `verifyBackup`/restore never hash or restore the metadata as a user file; for legacy backups a `manifest.json` entry is skipped (its on-disk bytes are old metadata, not user data).
2. **Safety backup skipped files:** `restoreBackup` aborts with `SAFETY_BACKUP_INCOMPLETE` (naming the skipped files) before any writes when the pre-restore safety backup is incomplete.
3. **Hash-before-copy race:** after each `copyFile`, the destination bytes are re-hashed and compared; on mismatch the partial backup dir is discarded, no DB row is recorded, and `BACKUP_COPY_MISMATCH` names the file.
4. **Restore terminal event:** the `backups.restore` IPC handler now emits `backup.completed` on success and `backup.failed` on failure, so the UI no longer sticks on "Backing up…".
5. **Steam userdata on secondary libraries:** userdata is searched under each Steam *client* install root (`<clientRoot>/userdata`), not derived from the game's library dir — `toInstalledGames` takes the client roots explicitly.

New regression tests (8): sibling-manifest preservation incl. byte-identical restore of a user-owned `manifest.json`; legacy in-tree metadata verify+restore; legacy collision skip; safety-backup-incomplete abort before any writes; deterministic hash-race failure; restore IPC `backup.completed`/`backup.failed` emission; secondary-library userdata discovery.

## Codex-review fixes, cycle 2 (2026-10-24, on `game-save-manager/initial-development`)

Both findings from the second Codex review of PR #4 were verified real and fixed:

1. **Restore blocked when the original save directory is missing:** `restoreBackup` took its pre-restore safety backup via `createBackup`, which threw `SAVE_DIR_MISSING` before the restore could recreate the directory — an intact backup was unrestorable after its save folder was deleted. The safety step now probes the destination: a *genuinely absent* folder (stat ENOENT with an existing directory ancestor) records an intentionally **empty safety snapshot** (label `pre-restore safety`, 0 files, explanatory note) and the restore proceeds to recreate the folder; an unreadable/disconnected destination (non-ENOENT stat failure, no directory ancestor, or the path exists but is not a folder) is still rejected with `SAVE_DIR_MISSING` before anything is written.
2. **Save folders containing the backup destination:** `createBackup` walked the save folder with no overlap check, so a manually registered folder containing `backupsRoot` swept every previous backup into each new snapshot (1, 3, 7, 15, … files). `createBackup` (and `restoreBackup`, before its safety step) now reject overlapping source/destination roots with the new `BACKUP_DESTINATION_OVERLAPS_SAVE_DIR` code — in either direction — before anything is walked or written.

New regression tests (5): restore-after-deletion recovery with empty safety snapshot (which itself verifies clean); restore rejection when the save path is a regular file; restore rejection when the destination is unreachable (ancestor not a directory); overlap rejection for a save folder containing backup storage; overlap rejection for a save folder inside backup storage. Full suite: **84/84 pass**, typecheck and lint clean (2026-10-24, Linux VM).

## Codex-review fixes, cycle 3 (2026-10-24, on `game-save-manager/initial-development`)

The single finding from the third Codex review of PR #4 was verified real and fixed:

1. **UNC syntax broken when prefixing long Windows paths:** `withLongPathPrefix` prepended `\\?\` directly to the resolved path, so a long UNC path `\\server\share\...` became the invalid `\\?\\server\share\...` instead of `\\?\UNC\server\share\...` — saves on network shares at ≥240 chars were rejected/skipped. The conversion now lives in the exported, platform-independent `win32LongPathPrefix` helper (built on `path.win32` semantics so it is testable on Linux) and delegates the namespacing to `path.win32.toNamespacedPath()` once the ≥240-char threshold is met; already-namespaced paths are returned untouched and short paths keep their previous resolved-but-unprefixed form. Windows filesystem behaviour itself was not executed — still pending real-Windows validation.

New regression tests (4, `tests/unit/long-path.test.ts`): long UNC → `\\?\UNC\` form (cross-checked against `path.win32.toNamespacedPath()`); long drive-letter → `\\?\` form; short UNC/drive paths unprefixed; already-namespaced long paths untouched. Full suite: **88/88 pass** (62 backend + 26 UI; baseline 84), typecheck and lint clean (2026-10-24, Linux VM).

## First milestone

Register a manual save folder, produce a dated, checksum-verified snapshot, list backups, and restore one with a safety copy and explicit confirmation. **Done.**

## Verified (2026-10-23, Linux VM)

- [x] Scaffold: package.json + lockfile, tsconfigs (strict), vite, vitest, eslint, electron-builder NSIS+zip config, dev/smoke scripts — `npm ci` clean.
- [x] `npm run typecheck` — renderer, main, preload all clean.
- [x] `npm run lint` — clean.
- [x] `npm run test` — **74/74 pass**: backend 50 (schemas 6, migrations 2, backup-engine 19, discovery 14, scheduler 7, ipc-handlers 2) + UI 24. Real fs fixtures under `os.tmpdir()` for backend; jsdom for UI.
- [x] `npm run build` — vite renderer + tsc main/preload succeed.
- [x] `npm run smoke` — production bundle opened a real Electron window under xvfb (`SMOKE_OK`).
- [x] SQLite schema: `games`, `backups`, `backup_files`, `schedules`, `schema_migrations`; migrations idempotent.
- [x] Backup engine: create (hash/copy/manifest/DB), change-detection skip, verify (checksum/size/missing), restore (`confirmed: true` gate, pre-restore safety backup, additive overwrite, post-restore check).
- [x] Locked/unreadable files skipped with warnings; missing save dir → actionable `SAVE_DIR_MISSING`.
- [x] Discovery: VDF parser, Steam libraries + manifests (corrupt skipped), Epic `.item` (corrupt skipped), Battle.net detection, candidates with `verified-path` / `pattern-match` evidence, case-insensitive dedup, no invented locations.
- [x] Scheduler: due-run, `last_run_at` bookkeeping, overlap guard, failure isolation; timers don't survive restarts (documented).
- [x] IPC: 15 channels + `games.chooseFolder` + 3 events, zod-validated, typed `window.saveManager` preload.
- [x] React UI (library, add-game, detail, verify, restore, schedules) built against the `shared/` contract; 24/24 UI tests pass.
- [x] Portable Windows zip built on Linux and contents-verified (gitignored, not committed).

## Pending (need Windows / owner)

- [ ] Real Steam discovery against an actual Steam install.
- [ ] Real Epic discovery against `%ProgramData%\Epic\...\Manifests`.
- [ ] Battle.net launcher detection on a real machine.
- [ ] `\\?\` long-path prefix behavior on paths ≥240 chars.
- [ ] Drive-letter paths (`D:\...`), disconnected-drive errors.
- [ ] Native folder picker (`games.chooseFolder`) in the packaged app.
- [ ] Locked-file skip with a real game holding saves open.
- [ ] Scheduler firing across sleep/wake and app restart.
- [ ] Portable zip first run on the owner's Windows machine.
- [ ] `npm run package:win` — NSIS installer builds and installs.
- [ ] Screenshots from the real app (no mock screenshots).

## Deliberately out of scope (MVP)

- Backup deletion / retention pruning — no deletion features at all.
- Battle.net game auto-discovery — manual registration only, by design.
- Restores never delete files unknown to the backup (additive overwrite).
- Scheduler does not backfill missed runs while the app was closed; timers do not survive reboots.
- No cloud sync, no per-file selective restore, no update mechanism.

## Next action

Owner review of PR #4. After merge, next milestone: backup retention settings, or proceed per the 17-project queue (Project 2: Concrete Operations Manager, already in development on `concrete-operations-manager/mvp`).

## Acceptance notes

- 2026-10-23: branch `game-save-manager/initial-development` rebased onto merged `main` (intake catalog `d4441fd`); docs reconciled to intake filenames (`docs/PRODUCT_SPEC.md`, `docs/IMPLEMENTATION_STATUS.md`); implementation-only files `docs/SPEC.md` and `docs/IMPLEMENTATION_TRACKER.md` folded in and removed.
- Do not infer success from the existence of planning documents — every claim above was executed on the Linux VM with evidence, or is explicitly marked pending.
