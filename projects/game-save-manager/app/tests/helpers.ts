/**
 * Real-filesystem fixtures for tests. Everything lives under os.tmpdir() and
 * is removed after each test — no fabricated results, no repo pollution.
 */
import type { DatabaseSync } from 'node:sqlite';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { openDatabase } from '../electron/main/db/database';
import { addGame } from '../electron/main/db/games';
import type { Game } from '../shared/types';

export interface Fixture {
  /** Root tmp dir for this fixture. */
  dir: string;
  db: DatabaseSync;
  backupsRoot: string;
  /** A scratch save folder with sample game saves. */
  saveDir: string;
  cleanup: () => void;
}

export function makeFixture(): Fixture {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'gsm-test-'));
  const db = openDatabase(':memory:');
  const backupsRoot = path.join(dir, 'backups');
  fs.mkdirSync(backupsRoot, { recursive: true });
  const saveDir = path.join(dir, 'saves');
  fs.mkdirSync(saveDir, { recursive: true });
  return {
    dir,
    db,
    backupsRoot,
    saveDir,
    cleanup: () => {
      try {
        db.close();
      } catch {
        // ignore
      }
      fs.rmSync(dir, { recursive: true, force: true });
    },
  };
}

/** Write a file under base at a forward-slash relative path. */
export function writeFile(base: string, rel: string, content: string | Buffer): string {
  const abs = path.join(base, ...rel.split('/'));
  fs.mkdirSync(path.dirname(abs), { recursive: true });
  fs.writeFileSync(abs, content);
  return abs;
}

export function readFile(base: string, rel: string): string {
  return fs.readFileSync(path.join(base, ...rel.split('/')), 'utf8');
}

/** Register a tracked game pointing at this fixture's save dir. */
export function addTestGame(fixture: Fixture, name = 'Test Game'): Game {
  return addGame(fixture.db, { name, savePath: fixture.saveDir, source: 'manual' });
}

/** Standard sample save tree used by the backup tests. */
export function seedSaveTree(saveDir: string): void {
  writeFile(saveDir, 'slot1.sav', 'save data v1');
  writeFile(saveDir, 'slot2.sav', 'second slot v1');
  writeFile(saveDir, 'config/settings.ini', 'volume=80\nfullscreen=true\n');
  writeFile(saveDir, 'screenshots/shot.png', Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x00, 0x01]));
}
