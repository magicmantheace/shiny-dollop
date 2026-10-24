/**
 * Backup engine integration tests against real filesystem fixtures.
 *
 * MVP acceptance: backup -> modify originals -> restore -> verify recovery.
 */
import { afterEach, describe, expect, it } from 'vitest';
import fs from 'node:fs';
import crypto from 'node:crypto';
import path from 'node:path';
import {
  createBackup,
  restoreBackup,
  siblingManifestPath,
  verifyBackup,
  walkSaveDir,
} from '../../electron/main/backup/engine';
import { BackupError, BackupErrorCodes } from '../../electron/main/backup/errors';
import { countBackups, getBackupDetail, insertBackup, listBackups } from '../../electron/main/db/backups';
import {
  addTestGame,
  makeFixture,
  readFile,
  seedSaveTree,
  writeFile,
  type Fixture,
} from '../helpers';

let fixture: Fixture | null = null;
afterEach(() => {
  fixture?.cleanup();
  fixture = null;
});

function setup(): Fixture {
  fixture = makeFixture();
  seedSaveTree(fixture.saveDir);
  return fixture;
}

describe('createBackup', () => {
  it('copies every file, writes a manifest, and records the DB rows', async () => {
    const f = setup();
    const game = addTestGame(f);
    const progress: string[] = [];

    const result = await createBackup(
      { db: f.db, backupsRoot: f.backupsRoot },
      game.id,
      { label: 'first', onProgress: (p) => progress.push(`${p.phase}:${p.done}/${p.total}`) },
    );

    expect(result.skipped).toBe(false);
    expect(result.backup.fileCount).toBe(4);
    expect(result.backup.totalBytes).toBeGreaterThan(0);
    expect(result.backup.label).toBe('first');
    expect(progress.length).toBeGreaterThan(0);

    // Files land on disk at their relative paths.
    expect(readFile(result.backup.backupDir, 'slot1.sav')).toBe('save data v1');
    expect(readFile(result.backup.backupDir, 'config/settings.ini')).toContain('volume=80');

    // Metadata lives as a SIBLING of the backup dir, never inside the tree.
    const manifest = JSON.parse(
      fs.readFileSync(siblingManifestPath(result.backup.backupDir), 'utf8'),
    ) as { files: { relPath: string; sha256: string }[] };
    expect(manifest.files).toHaveLength(4);
    expect(manifest.files.every((e) => /^[0-9a-f]{64}$/.test(e.sha256))).toBe(true);
    expect(fs.existsSync(path.join(result.backup.backupDir, 'manifest.json'))).toBe(false);

    // DB rows match.
    const detail = getBackupDetail(f.db, result.backup.id);
    expect(detail?.files).toHaveLength(4);
    expect(countBackups(f.db, game.id)).toBe(1);
  });

  it('skips creating a duplicate version when nothing changed', async () => {
    const f = setup();
    const game = addTestGame(f);
    const deps = { db: f.db, backupsRoot: f.backupsRoot };

    const first = await createBackup(deps, game.id);
    expect(first.skipped).toBe(false);

    const second = await createBackup(deps, game.id);
    expect(second.skipped).toBe(true);
    expect(second.reason).toMatch(/no changes/i);
    expect(second.backup.id).toBe(first.backup.id);
    expect(countBackups(f.db, game.id)).toBe(1);
  });

  it('creates a new version when a file changed, was added, or was removed', async () => {
    const f = setup();
    const game = addTestGame(f);
    const deps = { db: f.db, backupsRoot: f.backupsRoot };

    await createBackup(deps, game.id);
    writeFile(f.saveDir, 'slot1.sav', 'save data v2 — boss defeated');
    writeFile(f.saveDir, 'slot3.sav', 'brand new slot');
    fs.rmSync(path.join(f.saveDir, 'slot2.sav'));

    const second = await createBackup(deps, game.id);
    expect(second.skipped).toBe(false);
    expect(second.backup.fileCount).toBe(4); // slot1, slot3, settings, screenshot
    expect(countBackups(f.db, game.id)).toBe(2);
    expect(readFile(second.backup.backupDir, 'slot1.sav')).toBe('save data v2 — boss defeated');
  });

  it('throws an actionable error when the save folder is missing', async () => {
    const f = setup();
    const game = addTestGame(f);
    fs.rmSync(f.saveDir, { recursive: true });

    const err = await createBackup({ db: f.db, backupsRoot: f.backupsRoot }, game.id).catch(
      (e: unknown) => e,
    );
    expect(err).toBeInstanceOf(BackupError);
    expect((err as BackupError).code).toBe(BackupErrorCodes.SAVE_DIR_MISSING);
    expect((err as Error).message).toMatch(/re-register/i);
  });

  it('skips locked/unreadable files with a warning instead of crashing', async () => {
    const f = setup();
    const game = addTestGame(f);
    // A dangling symlink can never be read: exercises the skip path portably.
    try {
      fs.symlinkSync(
        path.join(f.saveDir, 'does-not-exist-target'),
        path.join(f.saveDir, 'locked.sav'),
      );
    } catch {
      // Windows without symlink privilege: fall back to the unreadable-dir
      // skip path, which walkSaveDir also handles gracefully.
      return;
    }

    const result = await createBackup({ db: f.db, backupsRoot: f.backupsRoot }, game.id);
    expect(result.skipped).toBe(false);
    expect(result.skippedFiles.some((s) => s.relPath === 'locked.sav')).toBe(true);
    expect(result.backup.fileCount).toBe(4);
  });

  it('walkSaveDir reports an unreadable directory as a skip, not a throw', async () => {
    const { files, skipped } = await walkSaveDir(path.join('definitely', 'not', 'here'));
    expect(files).toEqual([]);
    expect(skipped.length).toBeGreaterThan(0);
  });

  it('backs up cloud-sync conflict copies but flags them in the manifest notes', async () => {
    const f = setup();
    const game = addTestGame(f);
    writeFile(f.saveDir, 'progress (conflicted copy).sav', 'conflicted content');

    const result = await createBackup({ db: f.db, backupsRoot: f.backupsRoot }, game.id);
    expect(result.skipped).toBe(false);
    // The file IS backed up…
    expect(readFile(result.backup.backupDir, 'progress (conflicted copy).sav')).toBe(
      'conflicted content',
    );
    // …but flagged.
    expect(result.notes.some((n) => n.includes('conflict copy'))).toBe(true);
    expect(result.backup.notes).toMatch(/conflict copy/i);
  });
});

describe('verifyBackup', () => {
  it('reports ok for an intact backup', async () => {
    const f = setup();
    const game = addTestGame(f);
    const deps = { db: f.db, backupsRoot: f.backupsRoot };
    const created = await createBackup(deps, game.id);

    const result = await verifyBackup(deps, created.backup.id);
    expect(result.ok).toBe(true);
    expect(result.checkedFiles).toBe(4);
    expect(result.corrupt).toEqual([]);
  });

  it('detects a corrupted stored file (checksum mismatch)', async () => {
    const f = setup();
    const game = addTestGame(f);
    const deps = { db: f.db, backupsRoot: f.backupsRoot };
    const created = await createBackup(deps, game.id);

    // Tamper with a stored file: same size, different bytes -> checksum mismatch.
    const stored = path.join(created.backup.backupDir, 'slot1.sav');
    const original = fs.readFileSync(stored, 'utf8');
    expect(original.length).toBeGreaterThan(4);
    fs.writeFileSync(stored, 'X' + original.slice(1));

    const result = await verifyBackup(deps, created.backup.id);
    expect(result.ok).toBe(false);
    expect(result.corrupt).toHaveLength(1);
    expect(result.corrupt[0]?.relPath).toBe('slot1.sav');
    expect(result.corrupt[0]?.issue).toBe('checksum-mismatch');
    expect(result.corrupt[0]?.expected).toMatch(/^[0-9a-f]{64}$/);
    expect(result.corrupt[0]?.actual).toMatch(/^[0-9a-f]{64}$/);
    expect(result.corrupt[0]?.actual).not.toBe(result.corrupt[0]?.expected);
  });

  it('detects a missing stored file', async () => {
    const f = setup();
    const game = addTestGame(f);
    const deps = { db: f.db, backupsRoot: f.backupsRoot };
    const created = await createBackup(deps, game.id);

    fs.rmSync(path.join(created.backup.backupDir, 'slot2.sav'));

    const result = await verifyBackup(deps, created.backup.id);
    expect(result.ok).toBe(false);
    expect(result.corrupt.some((c) => c.relPath === 'slot2.sav' && c.issue === 'missing')).toBe(true);
  });
});

describe('restoreBackup — MVP acceptance', () => {
  it('backup -> modify originals -> restore -> verify recovery', async () => {
    const f = setup();
    const game = addTestGame(f);
    const deps = { db: f.db, backupsRoot: f.backupsRoot };

    // 1. Baseline backup (v1).
    const v1 = await createBackup(deps, game.id, { label: 'before the boss fight' });
    expect(v1.skipped).toBe(false);

    // 2. Modify the originals: change one file, add one, delete one.
    writeFile(f.saveDir, 'slot1.sav', 'CORRUPTED — do not want');
    writeFile(f.saveDir, 'autosave.sav', 'autosave after the crash');
    fs.rmSync(path.join(f.saveDir, 'config', 'settings.ini'));

    // 3. Restore v1 with explicit confirmation.
    const restored = await restoreBackup(deps, v1.backup.id, { confirmed: true });

    // 4. Verify recovery: every v1 file is byte-identical again…
    expect(readFile(f.saveDir, 'slot1.sav')).toBe('save data v1');
    expect(readFile(f.saveDir, 'slot2.sav')).toBe('second slot v1');
    expect(readFile(f.saveDir, 'config/settings.ini')).toContain('volume=80');
    // …the post-restore checksum pass is clean…
    expect(restored.mismatches).toEqual([]);
    expect(restored.restoredFiles).toBe(4);
    // …and the restore never deleted anything it didn't know about.
    expect(readFile(f.saveDir, 'autosave.sav')).toBe('autosave after the crash');
  });

  it('refuses to restore without explicit confirmed:true', async () => {
    const f = setup();
    const game = addTestGame(f);
    const deps = { db: f.db, backupsRoot: f.backupsRoot };
    const v1 = await createBackup(deps, game.id);

    const err = await restoreBackup(
      deps,
      v1.backup.id,
      // Intentionally wrong: the type only allows `true`; this proves the
      // runtime guard holds even if the type is bypassed.
      { confirmed: false } as unknown as { confirmed: true },
    ).catch((e: unknown) => e);

    expect(err).toBeInstanceOf(BackupError);
    expect((err as BackupError).code).toBe(BackupErrorCodes.RESTORE_NOT_CONFIRMED);
    // The save dir is untouched.
    expect(readFile(f.saveDir, 'slot1.sav')).toBe('save data v1');
    expect(countBackups(f.db, game.id)).toBe(1);
  });

  it('creates a pre-restore safety backup of the current state first', async () => {
    const f = setup();
    const game = addTestGame(f);
    const deps = { db: f.db, backupsRoot: f.backupsRoot };

    const v1 = await createBackup(deps, game.id, { label: 'v1' });
    writeFile(f.saveDir, 'slot1.sav', 'current progress I might want back');

    const restored = await restoreBackup(deps, v1.backup.id, { confirmed: true });

    // A safety backup was recorded with the exact label…
    const backups = listBackups(f.db, game.id);
    const safety = backups.find((b) => b.label === 'pre-restore safety');
    expect(safety).toBeDefined();
    expect(restored.safetyBackupId).toBe(safety?.id);
    // …and it captured the pre-restore state, not v1.
    expect(readFile(safety?.backupDir as string, 'slot1.sav')).toBe(
      'current progress I might want back',
    );
    // Restore itself still recovered v1.
    expect(readFile(f.saveDir, 'slot1.sav')).toBe('save data v1');
  });

  it('reports post-restore mismatches instead of silently succeeding', async () => {
    const f = setup();
    const game = addTestGame(f);
    const deps = { db: f.db, backupsRoot: f.backupsRoot };
    const v1 = await createBackup(deps, game.id);

    // Sabotage the stored backup so the post-restore check has something to find.
    // (Deleting one stored file makes restore throw BACKUP_DIR_MISSING instead —
    // that path is covered below; here we corrupt then restore: the corrupt
    // bytes get copied, and the post-restore hash flags the mismatch.)
    const stored = path.join(v1.backup.backupDir, 'slot1.sav');
    const detail = getBackupDetail(f.db, v1.backup.id);
    const manifestSha = detail?.files.find((e) => e.relPath === 'slot1.sav')?.sha256 as string;
    // Corrupt the stored file but keep the DB manifest: post-restore re-hash
    // compares save-dir content against the manifest and must flag it.
    fs.writeFileSync(stored, 'tampered!' + 'x'.repeat(100));

    const restored = await restoreBackup(deps, v1.backup.id, { confirmed: true });
    expect(restored.mismatches.some((m) => m.relPath === 'slot1.sav')).toBe(true);
    expect(manifestSha).toMatch(/^[0-9a-f]{64}$/);
  });
});
/**
 * Regression tests for the Codex-review fixes: manifest.json collision,
 * incomplete safety backups, and the hash-before-copy race.
 */

function sha256Hex(content: string): string {
  return crypto.createHash('sha256').update(content, 'utf8').digest('hex');
}

describe('manifest.json collision (regression)', () => {
  it('keeps a user-owned manifest.json intact: metadata goes to a sibling file', async () => {
    const f = setup();
    const game = addTestGame(f);
    writeFile(f.saveDir, 'manifest.json', '{"player":"adam","slot":1}');
    const deps = { db: f.db, backupsRoot: f.backupsRoot };

    const created = await createBackup(deps, game.id);
    expect(created.skipped).toBe(false);
    expect(created.backup.fileCount).toBe(5);

    // The user's own manifest.json is preserved byte-for-byte in the tree…
    expect(readFile(created.backup.backupDir, 'manifest.json')).toBe('{"player":"adam","slot":1}');
    // …and the backup metadata lives next to the tree, not inside it.
    const sibling = siblingManifestPath(created.backup.backupDir);
    expect(fs.existsSync(sibling)).toBe(true);
    const meta = JSON.parse(fs.readFileSync(sibling, 'utf8')) as {
      files: { relPath: string }[];
    };
    expect(meta.files.some((e) => e.relPath === 'manifest.json')).toBe(true);
    expect(fs.readFileSync(sibling, 'utf8')).not.toBe('{"player":"adam","slot":1}');

    // verifyBackup is clean…
    const verified = await verifyBackup(deps, created.backup.id);
    expect(verified.ok).toBe(true);
    expect(verified.checkedFiles).toBe(5);

    // …and a restore brings the user's manifest.json back byte-identical.
    writeFile(f.saveDir, 'manifest.json', '{"player":"adam","slot":99}');
    writeFile(f.saveDir, 'slot1.sav', 'save data v2');
    const restored = await restoreBackup(deps, created.backup.id, { confirmed: true });
    expect(restored.mismatches).toEqual([]);
    expect(readFile(f.saveDir, 'manifest.json')).toBe('{"player":"adam","slot":1}');
    expect(readFile(f.saveDir, 'slot1.sav')).toBe('save data v1');
  });

  it('legacy in-tree metadata still verifies and restores', async () => {
    const f = makeFixture(); // No seedSaveTree — hand-crafted legacy layout.
    const game = addTestGame(f);
    const deps = { db: f.db, backupsRoot: f.backupsRoot };

    // Current state of the save dir (what the restore will overwrite).
    writeFile(f.saveDir, 'slot1.sav', 'current progress');

    // Hand-crafted legacy backup: metadata INSIDE the tree, as old versions wrote it.
    const backupDir = path.join(f.backupsRoot, String(game.id), '2026-01-01T00-00-00-000Z');
    const saveBytes = 'legacy save v1';
    const fileEntry = {
      relPath: 'slot1.sav',
      sha256: sha256Hex(saveBytes),
      sizeBytes: Buffer.byteLength(saveBytes),
    };
    writeFile(backupDir, 'slot1.sav', saveBytes);
    writeFile(
      backupDir,
      'manifest.json',
      JSON.stringify({
        version: 1,
        gameId: game.id,
        label: 'legacy',
        createdAt: '2026-01-01T00:00:00.000Z',
        notes: [],
        skippedFiles: [],
        files: [fileEntry],
      }),
    );
    const backup = insertBackup(f.db, {
      gameId: game.id,
      label: 'legacy',
      fileCount: 1,
      totalBytes: fileEntry.sizeBytes,
      backupDir,
      notes: null,
      files: [fileEntry],
    });

    // Read logic finds the legacy in-tree manifest (no sibling exists)…
    const verified = await verifyBackup(deps, backup.id);
    expect(verified.ok).toBe(true);
    expect(verified.checkedFiles).toBe(1);

    // …and restore recovers the save without ever restoring metadata as a user file.
    const restored = await restoreBackup(deps, backup.id, { confirmed: true });
    expect(restored.mismatches).toEqual([]);
    expect(readFile(f.saveDir, 'slot1.sav')).toBe('legacy save v1');
    expect(fs.existsSync(path.join(f.saveDir, 'manifest.json'))).toBe(false);
  });

  it('legacy backup whose user manifest.json was destroyed: metadata is never restored as a user file', async () => {
    const f = makeFixture();
    const game = addTestGame(f);
    const deps = { db: f.db, backupsRoot: f.backupsRoot };

    // The save dir currently holds the user's real manifest.json.
    writeFile(f.saveDir, 'slot1.sav', 'current progress');
    writeFile(f.saveDir, 'manifest.json', '{"player":"adam","slot":7}');

    // Legacy backup where the old bug already destroyed the user's file: the
    // DB still lists the user's manifest.json entry (with the USER's hash),
    // but the bytes at <backupDir>/manifest.json are the old metadata.
    const backupDir = path.join(f.backupsRoot, String(game.id), '2026-01-01T00-00-00-000Z');
    const slotBytes = 'legacy save v1';
    const userManifestBytes = '{"player":"adam","slot":1}';
    const slotEntry = {
      relPath: 'slot1.sav',
      sha256: sha256Hex(slotBytes),
      sizeBytes: Buffer.byteLength(slotBytes),
    };
    const userManifestEntry = {
      relPath: 'manifest.json',
      sha256: sha256Hex(userManifestBytes),
      sizeBytes: Buffer.byteLength(userManifestBytes),
    };
    writeFile(backupDir, 'slot1.sav', slotBytes);
    writeFile(
      backupDir,
      'manifest.json',
      JSON.stringify({
        version: 1,
        gameId: game.id,
        label: 'legacy',
        createdAt: '2026-01-01T00:00:00.000Z',
        notes: [],
        skippedFiles: [],
        files: [userManifestEntry, slotEntry],
      }),
    );
    const backup = insertBackup(f.db, {
      gameId: game.id,
      label: 'legacy',
      fileCount: 2,
      totalBytes: slotEntry.sizeBytes + userManifestEntry.sizeBytes,
      backupDir,
      notes: null,
      files: [userManifestEntry, slotEntry],
    });

    // Verify must NOT certify this backup as intact: the user's manifest.json
    // entry is unrecoverable (its bytes were destroyed by the old metadata
    // write), so it is reported as corrupt/missing instead of being silently
    // skipped while still counted in checkedFiles.
    const verified = await verifyBackup(deps, backup.id);
    expect(verified.ok).toBe(false);
    expect(verified.checkedFiles).toBe(2);
    expect(verified.corrupt).toContainEqual(
      expect.objectContaining({ relPath: 'manifest.json', issue: 'missing' }),
    );

    // …and restore recovers slot1.sav without writing metadata bytes over the
    // user's current manifest.json.
    const restored = await restoreBackup(deps, backup.id, { confirmed: true });
    expect(restored.mismatches).toEqual([]);
    expect(restored.restoredFiles).toBe(1);
    expect(readFile(f.saveDir, 'slot1.sav')).toBe('legacy save v1');
    expect(readFile(f.saveDir, 'manifest.json')).toBe('{"player":"adam","slot":7}');
  });
});

describe('restoreBackup safety (regression)', () => {
  it('aborts before any writes when the pre-restore safety backup is incomplete', async () => {
    const f = setup();
    const game = addTestGame(f);
    const deps = { db: f.db, backupsRoot: f.backupsRoot };
    const v1 = await createBackup(deps, game.id);

    // A dangling symlink can never be read: the safety backup must skip it.
    try {
      fs.symlinkSync(
        path.join(f.saveDir, 'does-not-exist-target'),
        path.join(f.saveDir, 'locked.sav'),
      );
    } catch {
      return; // Windows without symlink privilege — same guard as the other symlink test.
    }
    const before = fs.readdirSync(f.saveDir).sort();

    const err = await restoreBackup(deps, v1.backup.id, { confirmed: true }).catch(
      (e: unknown) => e,
    );
    expect(err).toBeInstanceOf(BackupError);
    expect((err as BackupError).code).toBe(BackupErrorCodes.SAFETY_BACKUP_INCOMPLETE);
    expect((err as Error).message).toContain('locked.sav');

    // Aborted BEFORE any writes: originals untouched, nothing added or changed.
    expect(fs.readdirSync(f.saveDir).sort()).toEqual(before);
    expect(readFile(f.saveDir, 'slot1.sav')).toBe('save data v1');
    // The partial safety backup was still recorded (the escape hatch exists,
    // just incomplete) — but the restore itself never ran.
    expect(countBackups(f.db, game.id)).toBe(2);
  });
});

describe('createBackup walk-to-hash resize (regression)', () => {
  it('records the size of the bytes actually hashed when a file resizes after the walk', async () => {
    const f = setup();
    const game = addTestGame(f);
    const deps = { db: f.db, backupsRoot: f.backupsRoot };

    // Start from a 3-byte save.
    writeFile(f.saveDir, 'slot1.sav', 'abc');
    const sourcePath = path.join(f.saveDir, 'slot1.sav');
    const grown = 'grown-to-19-bytes!!'; // exactly 19 bytes
    expect(Buffer.byteLength(grown)).toBe(19);

    // Simulate the game resizing the save between the directory walk (which
    // stats 3 bytes) and hashing: the first read of the source file rewrites
    // it to 19 bytes, so the hash — and the copy — see the new contents.
    const origCreateReadStream = fs.createReadStream;
    let fired = false;
    fs.createReadStream = ((p: fs.PathLike, options?: unknown) => {
      if (!fired && String(p) === sourcePath) {
        fired = true;
        fs.writeFileSync(sourcePath, grown);
      }
      return (origCreateReadStream as (p: fs.PathLike, o?: unknown) => fs.ReadStream)(p, options);
    }) as typeof fs.createReadStream;
    let created;
    try {
      created = await createBackup(deps, game.id);
    } finally {
      fs.createReadStream = origCreateReadStream;
    }
    expect(fired).toBe(true);
    expect(created.skipped).toBe(false);

    // The manifest/DB entry must describe the bytes actually backed up (19),
    // not the stale walk-time size (3)…
    const detail = getBackupDetail(f.db, created.backup.id);
    const entry = detail?.files.find((e) => e.relPath === 'slot1.sav');
    expect(entry?.sizeBytes).toBe(19);
    expect(entry?.sha256).toBe(sha256Hex(grown));
    expect(readFile(created.backup.backupDir, 'slot1.sav')).toBe(grown);

    // …so the freshly created backup verifies clean instead of failing with
    // a size mismatch.
    const verified = await verifyBackup(deps, created.backup.id);
    expect(verified.ok).toBe(true);
    expect(verified.corrupt).toEqual([]);
  });
});

describe('createBackup hash-before-copy race (regression)', () => {
  it('fails the backup when a file changes between hashing and copying', async () => {
    const f = setup();
    const game = addTestGame(f);
    const deps = { db: f.db, backupsRoot: f.backupsRoot };

    // Deterministic hash race: every copy lands different bytes than the source.
    const origCopyFile = fs.promises.copyFile;
    fs.promises.copyFile = (async (src: string, dest: string) => {
      await origCopyFile(src, dest);
      // Simulate the game rewriting the save mid-backup: the destination
      // bytes no longer match the hash recorded moments earlier.
      await fs.promises.writeFile(dest, 'mid-backup rewrite by the game');
    }) as typeof fs.promises.copyFile;
    try {
      const err = await createBackup(deps, game.id).catch((e: unknown) => e);
      expect(err).toBeInstanceOf(BackupError);
      expect((err as BackupError).code).toBe(BackupErrorCodes.BACKUP_COPY_MISMATCH);
      // First file in walk order is config/settings.ini.
      expect((err as Error).message).toContain('config/settings.ini');
    } finally {
      fs.promises.copyFile = origCopyFile;
    }

    // No DB row was recorded…
    expect(countBackups(f.db, game.id)).toBe(0);
    // …and the partial backup dir was discarded.
    expect(fs.readdirSync(path.join(f.backupsRoot, String(game.id)))).toEqual([]);
  });
});
