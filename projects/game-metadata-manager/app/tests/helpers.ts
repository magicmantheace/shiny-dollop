import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import type { DatabaseSync } from 'node:sqlite';
import { openDatabase } from '../db/schema.js';
import { scanRoots, titleFromExeName, gameIdFor } from '../engine/scanner.js';
import { Library } from '../engine/library.js';
import { ArtworkStore } from '../engine/artwork.js';
import { ChangeLog } from '../engine/changes.js';
import { BundleIO } from '../engine/bundle.js';
import type { Game } from '../shared/ipc-contract.js';

export interface TestContext {
  dir: string;
  db: DatabaseSync;
  library: Library;
  artwork: ArtworkStore;
  changes: ChangeLog;
  bundles: BundleIO;
  dispose: () => void;
}

export function makeContext(): TestContext {
  const dir = mkdtempSync(join(tmpdir(), 'gmm-test-'));
  const db = openDatabase(join(dir, 'gmm.db'));
  const library = new Library(db);
  const artwork = new ArtworkStore(db, join(dir, 'artwork-cache'));
  const changes = new ChangeLog(db);
  const bundles = new BundleIO(library, artwork, changes);
  return {
    dir,
    db,
    library,
    artwork,
    changes,
    bundles,
    dispose: () => {
      db.close();
      rmSync(dir, { recursive: true, force: true });
    },
  };
}

/** Minimal valid PNG (signature + IHDR header only — enough for magic-byte checks). */
export function minimalPng(): Buffer {
  const sig = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);
  const ihdr = Buffer.alloc(25);
  ihdr.writeUInt32BE(13, 0); // length
  ihdr.write('IHDR', 4);
  ihdr.writeUInt32BE(1, 8); // width
  ihdr.writeUInt32BE(1, 12); // height
  ihdr[16] = 8; // bit depth
  ihdr[17] = 2; // truecolor
  return Buffer.concat([sig, ihdr]);
}

/** Minimal valid JPEG (SOI + JFIF-ish prefix). */
export function minimalJpeg(): Buffer {
  return Buffer.from([0xff, 0xd8, 0xff, 0xe0, 0x00, 0x10, 0x4a, 0x46, 0x49, 0x46]);
}

export function makeGame(overrides: Partial<Game> = {}): Game {
  const now = new Date().toISOString();
  return {
    id: 'game-' + Math.random().toString(36).slice(2),
    title: 'Test Game',
    originalTitle: 'Test Game',
    description: 'A fixture game',
    installPath: 'C:/Games/TestGame/game.exe',
    artworkId: null,
    tagIds: [],
    collectionIds: [],
    missing: false,
    createdAt: now,
    updatedAt: now,
    ...overrides,
  };
}

export { scanRoots, titleFromExeName, gameIdFor, mkdirSync, writeFileSync, join };

/** First game of an import result; throws if the import found nothing. */
export function firstGame(games: Game[]): Game {
  const g = games[0];
  if (!g) throw new Error('fixture import returned no game');
  return g;
}
