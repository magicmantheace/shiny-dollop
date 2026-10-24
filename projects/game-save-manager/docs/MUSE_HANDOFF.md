# Muse implementation handoff — Universal Game Save Manager

**Priority:** 1/17. **Project:** `projects/game-save-manager/`.
**Status:** MVP built and verified on Linux (2026-10-23); branch `game-save-manager/initial-development`, PR shiny-dollop #4 open and unmerged. Windows-only validation pending on the owner's machine.

## Assignment

Safely discover, back up, version, verify, and restore PC game saves across manual locations and common storefront layouts.

### Start here

1. Read repository-root `AGENTS.md` and this project's `AGENTS.md`.
2. Inspect the latest `main` and all relevant unmerged branches/PRs. Do not overwrite someone else's work.
3. Begin a dedicated `game-save-manager/mvp` branch once this intake has been merged (or base appropriately without rewriting history).
4. Choose the simplest maintainable stack compatible with: Electron + React + TypeScript + SQLite; filesystem operations through a validated main-process API.
5. Implement the **actual** MVP: Register a manual save folder, produce a dated, checksum-verified snapshot, list backups, and restore one with a safety copy and explicit confirmation.
6. Write automated tests for its success path and critical failure modes. Execute `docs/TEST_PLAN.md` where the environment permits.
7. Commit scope-limited production code, validate the build, and open an unmerged PR documenting evidence and limitations.
8. Update `docs/IMPLEMENTATION_STATUS.md`; do not claim unverified capabilities work.

### Expansion backlog

- Manual game/save-folder registration ✅
- Steam, Epic, and Battle.net location discovery where reliable ✅
- Versioned timestamped backups and per-file checksums ✅
- Safe restoration with pre-restore backup ✅
- Change detection ✅ and backup retention settings ⏳ (not in MVP)
- Scheduled backups while running ✅
- History, searchable game list, and exportable manifest ✅

### Project-specific guardrails

Do not assume storefront installation paths equal game save locations. Do not delete game data, bypass cloud sync, or silently overwrite saves.

**Integrations:** Standalone; optional future interoperability with the existing Universal PC Game Launcher only by separate approval.

Do not access or modify the other project directories, the original Crawl repository, real personal data, connected accounts, or production systems to test this app. Use fixtures or explicitly approved narrow interfaces.

### Stop/continue logic

Finish a small, functional vertical slice rather than scaffolding all 17 projects. If blocked by platform or a genuinely missing dependency, record the blocker, preserve reviewable work, and then proceed to another independent approved task.

---

## Build record (MVP, 2026-10-23)

**Stack chosen:** Electron 45 + React 19 + TypeScript (strict) + Vite, vitest, zod 4, `node:sqlite` (zero native builds), electron-builder (NSIS + zip, win x64). Mirrors `projects/universal-game-launcher/app` conventions.

**Branch note:** the implementation was built on `game-save-manager/initial-development` (cut from `main` before the intake catalog was merged, hence the name); rebased onto the merged `main` and docs reconciled to the intake filenames on 2026-10-23.

**What was built:**
- **SQLite** (`app/electron/main/db/`): `games`, `backups`, `backup_files`, `schedules` (+ `schema_migrations`); idempotent migrations. DB at `<userData>/data/savemanager.db`; backups at `<userData>/SaveManager/backups/<gameId>/<ISO-timestamp>/`.
- **Backup engine** (`app/electron/main/backup/engine.ts`): `createBackup` (walk → SHA-256 → change-detect → copy → `manifest.json`; skips duplicate versions), `verifyBackup` (re-hash vs manifest → `{ok, corrupt}`), `restoreBackup` (requires `confirmed: true`; `pre-restore safety` backup first; additive overwrite; post-restore checksum report). Locked/unreadable files skipped with warnings, never fatal. Cloud-sync conflict copies backed up but flagged. Originals never modified/deleted.
- **Discovery** (`app/electron/main/discovery/`): Steam `libraryfolders.vdf` + `appmanifest_*.acf` (read-only), Epic `.item` JSON (read-only), Battle.net client detection only. Candidates only from real local evidence with `verified-path` | `pattern-match` | `manual` labels; case-insensitive dedup.
- **Scheduler** (`app/electron/main/scheduler/`): per-game `interval_minutes` (5–43200), 60s tick, overlap-guarded; `last_run_at` on success only. Timers don't survive restarts (documented).
- **IPC** (`app/shared/`, handlers, preload): 15 channels + `games.chooseFolder` + 3 events; zod-validated; typed `window.saveManager`.
- **React UI:** game library, add-game dialog (native folder picker + evidence-labeled candidates), game detail, backup detail/verify, restore confirm (typed `RESTORE`), schedules view, aria-live toasts.

**Verification (Linux VM):** 66/66 tests, typecheck, lint, build, smoke (`SMOKE_OK` under xvfb) — all green, independently re-run by reviewer. MVP acceptance demo passed (backup → modify → restore → byte-identical). Portable Windows zip built and contents-verified. See `docs/TEST_PLAN.md` and `docs/IMPLEMENTATION_STATUS.md` for the full ledger.
