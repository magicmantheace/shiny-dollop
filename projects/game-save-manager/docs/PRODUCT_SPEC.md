# Product specification — Universal Game Save Manager

**Intake status:** MVP implemented and verified on Linux 2026-10-23 (PR shiny-dollop #4, unmerged); Windows-only validation pending.
**Priority:** 1/17
**Audience/target platform:** Windows desktop

## Problem and outcome

Safely discover, back up, version, verify, and restore PC game saves across manual locations and common storefront layouts.

## MVP user workflow and acceptance contract

Register a manual save folder, produce a dated, checksum-verified snapshot, list backups, and restore one with a safety copy and explicit confirmation.

The MVP is accepted only when a tester can complete the workflow using an actual running build, inspect the resulting data/artifact, restart when relevant, and reproduce the result. Showing an interface or a unit test alone is not an MVP.

## Requirements — initial and subsequent milestones

1. **Manual game/save-folder registration** — implement with persisted, validated state and meaningful user feedback where relevant.
2. **Steam, Epic, and Battle.net location discovery where reliable** — implement with persisted, validated state and meaningful user feedback where relevant.
3. **Versioned timestamped backups and per-file checksums** — implement with persisted, validated state and meaningful user feedback where relevant.
4. **Safe restoration with pre-restore backup** — implement with persisted, validated state and meaningful user feedback where relevant.
5. **Change detection and backup retention settings** — implement with persisted, validated state and meaningful user feedback where relevant.
6. **Scheduled backups while running** — implement with persisted, validated state and meaningful user feedback where relevant.
7. **History, searchable game list, and exportable manifest** — implement with persisted, validated state and meaningful user feedback where relevant.

## Data model and architecture considerations

Electron + React + TypeScript + SQLite; filesystem operations through a validated main-process API.

Use a clearly versioned and documented local storage/export format. Define entities and transitions from the MVP workflow, not guessed integrations. Include migration and backup/restore behavior before treating persisted data as production-ready.

## Integration strategy

Standalone; optional future interoperability with the existing Universal PC Game Launcher only by separate approval.

No other application's source or database may be modified as part of this project. Where useful, exchange versioned export/import contracts and independently owned fixtures.

## Nonfunctional and safety requirements

Do not assume storefront installation paths equal game save locations. Do not delete game data, bypass cloud sync, or silently overwrite saves.

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

## Appendix A — As-built behavior notes (MVP v0.1.0, 2026-10-23)

The following was written against the code as built. Where this appendix and the requirements above disagree, the requirements above win — file a bug.


### What the app does

Game Save Manager discovers where PC games keep their save files, takes
versioned, checksummed backups of those folders, and restores them — with
an automatic safety backup before every restore. It targets Windows 11 x64.
It never touches game installations; it only reads save folders and writes
backups (and, on restore, writes files back into the save folder).

Primary user story: a player about to mod, reinstall, or repair a game
takes one click to snapshot their saves; if anything breaks, they restore a
prior version with one more click.

### Features and behavior

#### 1. Game tracking

- A **game** is `{ id, name, savePath, source, createdAt }`. `savePath` is
  the absolute path of the folder whose contents are backed up.
- Games are added manually (native folder picker via `games.chooseFolder`)
  or promoted from a discovery candidate. `source` records which route was
  used: `manual | steam | epic | battlenet | discovered`.
- Games can be renamed or have their save path changed (`games.update`),
  and removed (`games.remove`). Removing a game removes its DB rows; it
  does **not** delete any backup files on disk (there are no deletion
  features in the MVP — see Non-goals).

#### 2. Discovery (read-only, honest)

Discovery never invents a save location. Every candidate carries an
**evidence label** plus a human-readable `detail` explaining why the path
is a candidate:

| Label | Meaning |
|---|---|
| `verified-path` | A concrete path with hard local evidence, e.g. Steam's `userdata/<user-id>/<appid>/` directory tied to a real `appmanifest_*.acf` install record. |
| `pattern-match` | A plausible save folder found by fuzzy name matching in known save roots (`Documents\My Games`, `AppData\Local`, `AppData\Roaming`, `Saved Games`). Should be confirmed by the user. |
| `manual` | The user pointed at it themselves (primary registration path). |

- **Steam** — parses `libraryfolders.vdf` for library roots, then reads each
  library's `steamapps/appmanifest_*.acf` (both read-only). Corrupt
  manifests are skipped, never fatal. Save candidates are derived from
  `userdata/<id>/<appid>/` (evidence `verified-path`).
- **Epic** — reads `.item` JSON manifests from
  `%ProgramData%\Epic\EpicGamesLauncher\Data\Manifests` (read-only).
  Corrupt items are skipped.
- **Battle.net** — client **detection only** (launcher executable present or
  not). Battle.net exposes no honest local registry of game save folders,
  so Battle.net games are registered **manually only**, by design.
- Candidates are deduplicated case-insensitively (Windows paths). Locations
  with no evidence are never listed. Discovery itself is read-only: it
  never writes to any store client's directories.

#### 3. Versioned backups

- `backups.create { gameId, label? }` walks the save folder and for every
  file computes **SHA-256** and size.
- **Change detection:** if every file's hash matches the latest backup, no
  new version is created — the call returns `skipped: true` with the
  existing backup. A new version is created when any file changed, was
  added, or was removed.
- Backup storage layout:
  `<userData>/SaveManager/backups/<gameId>/<ISO-8601-timestamp>/` —
  a plain copy of the folder tree plus a `manifest.json` recording every
  file's relative path, SHA-256, and size.
- Locked or unreadable files (e.g. a game holding a save open, a dangling
  symlink) are **skipped with warnings** (`skippedFiles` in the result),
  never fatal — the rest of the backup completes.
- Cloud-sync conflict copies (filenames containing `-CONFLICT` or
  `conflicted copy`) are backed up like any file but **flagged in the
  manifest notes**, since they may duplicate real saves.
- Originals are **never modified or deleted** by the backup engine.
- Progress is streamed over IPC (`backup.progress` with
  `phase: 'hash' | 'copy'`, `done/total`, `currentFile`), then
  `backup.completed` / `backup.failed` events.

#### 4. Verification

- `backups.verify { backupId }` re-hashes every file on disk in the backup
  directory against the manifest and returns
  `{ ok, checkedFiles, corrupt: [{ relPath, issue, expected?, actual? }] }`.
- Issues detected: `missing` (file gone), `checksum-mismatch` (content
  changed), `size-mismatch`. Verification is read-only.

#### 5. Restore (with automatic safety backup)

- `backups.restore { backupId, confirmed }` — `confirmed` must be literally
  `true` (enforced by zod; falsy/missing/string values are rejected with
  `RESTORE_NOT_CONFIRMED`). There is no quiet default.
- Before writing anything, the engine takes a **pre-restore safety backup**
  of the *current* save-folder state (label `pre-restore safety`) and
  returns its id as `safetyBackupId`. If the restore goes wrong, the safety
  backup is the escape hatch.
- Restore is an **additive overwrite**: backup files are copied over the
  save folder. Files present in the save folder but unknown to the backup
  are **left alone, never deleted**.
- After copying, every restored file is checksummed; the result reports
  `restoredFiles` and `mismatches` (expected empty on a clean restore).
- Restore never touches files outside the game's registered save path.

#### 6. Scheduler

- Per-game schedule: `schedules.set { gameId, intervalMinutes (5–43200), enabled? }`
  (upsert). `lastRunAt` is recorded on successful runs only.
- While the app is running, a 60-second tick finds schedules that are due
  and fires `createBackup` (labeled `scheduled backup`). Runs are
  overlap-guarded — a game never backs up twice concurrently.
- A due run whose saves are unchanged still counts as a run: it returns the
  unchanged-latest backup (`skipped: true`) and advances `lastRunAt`, so it
  does not spam the schedule every tick.
- A failed run (e.g. save dir vanished → `SAVE_DIR_MISSING`) emits
  `backup.failed` and leaves `lastRunAt` untouched, so the schedule stays
  due and retries. One failing game does not block the others.
- **Explicit limitation:** timers live only while the app runs. Missed runs
  while the app was closed are **not backfilled** — an overdue schedule is
  simply "due" at the next tick after launch. Scheduler state is in the DB;
  timers do not survive reboots. (This is by design for the MVP.)

### Data model

SQLite via `node:sqlite` (no native builds). DB file:
`<userData>/data/savemanager.db`.

- `games` — `id, name, save_path, source, created_at`
- `backups` — `id, game_id, created_at, label, file_count, total_bytes,
  backup_dir, notes`
- `backup_files` — `backup_id, rel_path, sha256, size_bytes` (one row per
  file per backup; full copy per version, not deltas)
- `schedules` — `id, game_id, interval_minutes, enabled, last_run_at`
- `schema_migrations` — applied migration versions (migrations idempotent)

All timestamps are ISO-8601 UTC strings; sizes are bytes; file paths in the
DB/manifest use forward-slash relative paths (portable).

### IPC surface (summary)

The full contract is `app/shared/` (channels, zod schemas, domain types) —
that directory is the source of truth. All payloads are zod-validated in
`electron/main/ipc/handlers.ts`; every response uses the envelope
`{ ok: true, data }` / `{ ok: false, error: { code, message } }`, exposed to
the renderer as the typed `window.saveManager` bridge.

Channels (15): `games.list`, `games.add`, `games.update`, `games.remove`,
`games.discoverCandidates`, `games.chooseFolder`, `backups.create`,
`backups.list`, `backups.get`, `backups.verify`, `backups.restore`,
`schedules.list`, `schedules.set`, `schedules.delete`.

Push events: `backup.progress`, `backup.completed`, `backup.failed`.

Error codes: `GAME_NOT_FOUND`, `SAVE_DIR_MISSING` (actionable message),
`BACKUP_NOT_FOUND`, `BACKUP_DIR_MISSING`, `RESTORE_NOT_CONFIRMED`,
`INVALID_INPUT`, `INTERNAL_ERROR`, `BACKUP_FAILED`.

### Explicit non-goals (MVP)

- **No backup deletion / retention pruning.** Storage grows with versions;
  the user deletes folders by hand if needed. (Deletion features were
  deliberately excluded to keep restore guarantees simple.)
- **No cloud sync** — backups live on the local machine only.
- **No diff UI or per-file selective restore** — restore is whole-backup.
- **No Battle.net game auto-discovery** — manual registration only.
- **No scheduler backfill / cross-reboot scheduling** — timers are
  in-app only (documented limitation, not a bug).
- **No update mechanism** in the MVP — the user downloads a new build.
- **Windows-only.** No macOS/Linux packaging; `node:path` is used
  throughout and POSIX-specific behavior is not targeted.

### Current limitations (see also README)

The app was built and tested on a Linux VM; every Windows-only behavior is
**pending validation on real Windows hardware** and is never claimed
otherwise: real Steam/Epic/Battle.net discovery, `\\?\` long-path handling,
drive-letter paths, the native folder picker in the packaged app, locked
files held open by a real game, scheduler behavior across sleep/restart,
and the install/package flow. No backup deletion/retention exists. The NSIS
installer was not assembled on this Linux VM (no Wine).
