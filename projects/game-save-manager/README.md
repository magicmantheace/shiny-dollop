# Universal Game Save Manager

**Status:** MVP functional / review ready — backend 42/42 tests + React UI 24/24 tests (**66/66 green**, 2026-10-23), typecheck, lint, build, and a production window smoke test all passing on Linux. Portable Windows zip built. Windows-only behaviors are **pending validation on real Windows hardware** (see "Unfinished features / known limitations"). Pull request: shiny-dollop #4 (unmerged).

**Priority:** 1 of 17 in the approved intake queue.
**Category:** Windows desktop
**Repository workspace:** `projects/game-save-manager/`

> **Screenshots:** none yet — screenshots must come from the real app on the owner's Windows machine. No mock screenshots are used anywhere in this repo.

## Purpose

Safely discover, back up, version, verify, and restore PC game saves across manual locations and common storefront layouts.

## First usable release (MVP)

Register a manual save folder, produce a dated, checksum-verified snapshot, list backups, and restore one with a safety copy and explicit confirmation. **Done and verified** — see "Verification" below.

## Features (as built)

- **Game library** — track games, each pointing at a save folder. Add via the native folder picker (manual, primary path) or promote a discovery candidate. Rename / re-point / remove games.
- **Honest discovery** — Steam via `libraryfolders.vdf` + `appmanifest_*.acf` (read-only), Epic via `.item` manifests (read-only), Battle.net = client detection only. Save-folder candidates come only from real local evidence and carry an evidence label (`verified-path` | `pattern-match` | `manual`); unverifiable locations are never listed.
- **Versioned backups** — SHA-256 every file; change detection skips creating a duplicate version when nothing changed. Backups live under `%APPDATA%\game-save-manager\SaveManager\backups\<gameId>\<timestamp>\` with a `manifest.json`. Originals are never modified or deleted. Live progress is shown while a backup runs.
- **Verify** — re-hash stored files against the manifest; reports missing files, checksum mismatches, and size mismatches.
- **Restore with safety backup** — restore requires typing `RESTORE`, takes a `pre-restore safety` backup of the current state first, then overwrites additively (files unknown to the backup are left alone) and reports post-restore checksums.
- **Scheduler** — per-game backup interval (5 min – 30 days); due schedules fire while the app runs, update `last_run_at`, and emit progress events. No backfill (documented design); timers do not survive app restarts.

Full behavior spec: `docs/PRODUCT_SPEC.md`. IPC contract: `app/shared/`.

## Full intended capabilities

- Manual game/save-folder registration ✅
- Steam, Epic, and Battle.net location discovery where reliable ✅
- Versioned timestamped backups and per-file checksums ✅
- Safe restoration with pre-restore backup ✅
- Change detection ✅ and backup retention settings ⏳ (not in MVP — no deletion/retention yet)
- Scheduled backups while running ✅
- History, searchable game list, and exportable manifest ✅

## Quick start (dev)

```bash
cd projects/game-save-manager/app
npm ci
npm run dev        # Vite + tsc watch + Electron (xvfb on headless Linux)
```

Prerequisites: Node.js ≥ 22. Nothing is installed or configured outside this project folder.

## Tests

```bash
cd projects/game-save-manager/app
npm run typecheck  # tsc --noEmit (renderer, main, preload)
npm run lint       # eslint
npm run test       # vitest run — 66/66 green (42 backend + 24 UI)
npm run build      # typecheck + vite + tsc
npm run smoke      # production bundle opens a real window (xvfb on Linux)
```

Backend tests use real filesystem fixtures under `os.tmpdir()`; UI tests use Testing Library + jsdom. No fabricated results.

## Verification (2026-10-23, Linux VM)

- `npm test`: **66/66 pass** (independent re-run by reviewer; an earlier 4-failure run was traced to a full `/tmp` breaking the Electron binary install in the review worktree — environment issue, not code).
- **MVP acceptance demo passed:** backup → modify originals → restore → byte-identical recovery; safety backup present with pre-restore state; post-restore checksums clean. Also covered: change-detection skip, checksum-mismatch detection, locked-file graceful skip, missing-dir actionable error, restore refused without confirmation.
- Portable Windows zip builds: `Game Save Manager-0.1.0-win-x64.zip` (~147 MB; contents verified, gitignored, not committed). NSIS installer not attempted (no Wine here); reproducible Windows build steps in `docs/WINDOWS_INSTALL.md`.

## Unfinished features / known limitations

- Windows-only behaviors unverified here: real Steam/Epic/Battle.net discovery, native folder picker, `\\?\` long paths, drive letters, NTFS locked files, scheduler across sleep/restart, portable-zip first launch on Windows.
- No backup deletion or retention policies yet.
- No code signing (SmartScreen will warn); default Electron icon.

## Dependencies and boundaries

Standalone; optional future interoperability with the existing Universal PC Game Launcher only by separate approval.

Do not assume storefront installation paths equal game save locations. Do not delete game data, bypass cloud sync, or silently overwrite saves.

## Muse start point

Read the repository-root `AGENTS.md`, then [this project's instructions](AGENTS.md) and [development handoff](docs/MUSE_HANDOFF.md). Implement the smallest working end-to-end milestone; document genuine test results. See [specification](docs/PRODUCT_SPEC.md), [test plan](docs/TEST_PLAN.md), and [status](docs/IMPLEMENTATION_STATUS.md).
