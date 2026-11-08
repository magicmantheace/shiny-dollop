# Test plan — Universal Game Save Manager

**Current test status:** 66/66 automated tests passing (2026-10-23, Linux VM); end-to-end MVP workflow demonstrated via automated tests on real fixtures; Windows-only execution pending.

## Required automated and integration scenarios

- Create and verify a snapshot of a fixture save folder
- Alter fixture files and restore byte-for-byte
- Deny restoration without explicit confirmation
- Handle missing locations, locked files, and interrupted writes
- Never modify a save during discovery or backup

## Cross-cutting tests

- Validate malformed, missing, oversized and unauthorized inputs.
- Confirm persistence, restart behavior, schema versioning, and export/import consistency where relevant.
- Exercise cancellation, timeouts, incomplete operations and recovery behavior.
- Confirm tests use temporary fixtures and do not read owner's private or production data.
- Verify deterministic calculations and no accidental state changes in read-only actions.

## End-to-end MVP verification

Register a manual save folder, produce a dated, checksum-verified snapshot, list backups, and restore one with a safety copy and explicit confirmation.

Run this workflow against a real application build using disposable data; record actual commands, OS environment, relevant results and any platform-only gaps. If the workflow requires Windows or local AI services unavailable in the worker environment, mark it **implemented but unverified** rather than passing.

## Mandatory verification record

For each run, capture: commit SHA, command, execution environment, passed/failed/skipped counts, observed UI/CLI behavior, defect links, and next action. Keep logs free of credentials and personal data.

No release or owner-acceptance claim before end-to-end demonstration.

---

## Appendix — Automated test record (2026-10-23, Linux VM)

The following was recorded by the implementation team and independently re-verified by the reviewer (66/66 green). An earlier 4-failure run during review was traced to a full `/tmp` breaking the Electron binary install in the review worktree — an environment issue, not a code defect.


Real filesystem fixtures under `os.tmpdir()`; nothing fabricated.

**tests/unit/schemas.test.ts** (6)
- `gameAddSchema` trims, requires non-empty name/savePath, defaults source to `manual`
- `backupRestoreSchema` requires `confirmed` to be literally `true` (rejects `false`, missing, `'yes'`)
- `backupCreateSchema` requires positive game id
- `scheduleSetSchema` bounds `intervalMinutes` to 5–43200, rejects fractions

**tests/unit/migrations.test.ts** (2)
- Fresh DB creates `games`, `backups`, `backup_files`, `schedules`, `schema_migrations` with the specified columns
- `runMigrations` is idempotent

**tests/integration/backup-engine.test.ts** (14)
- createBackup copies every file, writes `manifest.json`, records DB rows, streams progress
- **Change-detection skip**: second identical backup returns `skipped: true`, no new DB row
- New version on file change / add / remove
- Missing save dir → `SAVE_DIR_MISSING` with actionable message
- Locked/unreadable file (dangling symlink) → skipped with warning, backup succeeds
- Unreadable directory → reported as skip, not thrown
- Cloud-sync conflict copies backed up but flagged in notes
- verifyBackup: ok on intact; flags checksum-mismatch (with expected/actual hashes); flags missing files
- **MVP acceptance**: backup → modify originals → restore → byte-identical recovery; unknown-to-backup files left alone; post-restore mismatches empty
- restore refuses without `confirmed: true` (runtime guard, type bypassed); save dir untouched
- **Pre-restore safety backup** recorded with label `pre-restore safety`, capturing pre-restore state
- Post-restore checksum mismatch reported, not silently swallowed

**tests/integration/discovery.test.ts** (13)
- VDF parser: nested objects, escaped quotes, truncated input throws
- Steam: `libraryfolders.vdf` + valid `appmanifest_*.acf` read; corrupt manifest skipped; missing dir → `[]`
- Epic: `.item` JSON read; corrupt item skipped; missing dir → `[]`
- Battle.net: detected when launcher exe exists; not detected otherwise
- Candidates: Steam `userdata/<id>/<appid>/` → `verified-path`; name match in save roots → `pattern-match` (with "confirm" guidance); no candidates invented for games without evidence; case-insensitive dedup
- `runDiscovery` combines scans, reports counts + Battle.net status, every candidate carries a valid evidence label + detail

**tests/integration/scheduler.test.ts** (7)
- Due schedule runs, records `last_run_at`, emits `backup.completed`
- Not re-run before interval; overdue-but-unchanged run skips backup while advancing `last_run_at`
- Fresh backup when saves changed; labeled `scheduled backup`
- Disabled schedules never run
- Failure emits `backup.failed` with `SAVE_DIR_MISSING`; `last_run_at` untouched (stays due, retries)
- One failing game doesn't stop other due schedules
- `start`/`stop` timer control; no double-registration

### Manual / platform checks (pending — need a Windows machine)

See `docs/IMPLEMENTATION_TRACKER.md` "Pending" ledger. Minimum before calling
the MVP done on Windows:

1. Install the packaged app; register a game via the native folder picker.
2. Create a backup of a real game's save folder; confirm files + `manifest.json` on disk.
3. Verify backup → `ok: true`.
4. Modify a save, restore, confirm in-game state reverted and safety backup exists.
5. Run Steam/Epic discovery against real clients; confirm candidates and evidence labels; confirm nothing invented.
6. Set a 5-minute schedule; confirm it fires while the app runs and `last_run_at` advances.
7. Restart the app; confirm schedules persist (DB) and overdue ones are due.
8. Long-path save folder (≥240 chars) backs up without errors.
9. Locked file (game running, file open) → skipped with warning, no crash.
10. `npm run package:win` produces an installable NSIS installer.
