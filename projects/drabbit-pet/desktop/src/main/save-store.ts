import fs from 'node:fs';
import path from 'node:path';
import { parse, serialize, type SaveEnvelope } from 'drabbit-core';

/**
 * Owns the pet's save file on disk. Electron-free: the directory is
 * injected, so tests run against a temp folder.
 *
 * Writes are atomic (temp file + rename in the same directory) so a
 * crash mid-write can never leave a truncated save behind.
 */

export const SAVE_FILENAME = 'drabbit-save.json';

export type LoadOutcome = 'loaded' | 'fresh-missing' | 'fresh-corrupt';

export interface LoadResult {
  envelope: SaveEnvelope;
  outcome: LoadOutcome;
  /** Where a corrupt save was preserved (only for 'fresh-corrupt'). */
  backupPath?: string;
}

export class SaveStore {
  readonly filePath: string;

  constructor(
    dir: string,
    private readonly log: (msg: string) => void = () => undefined,
  ) {
    this.filePath = path.join(dir, SAVE_FILENAME);
  }

  /**
   * Load the save, or produce a fresh one via `createFresh`:
   * - missing file → fresh (first run)
   * - unparseable / invalid file → the corrupt file is renamed aside
   *   (never silently destroyed), a fresh save is created, and the
   *   recovery is logged.
   */
  loadOrCreate(nowMs: number, createFresh: (nowMs: number) => SaveEnvelope): LoadResult {
    let text: string;
    try {
      text = fs.readFileSync(this.filePath, 'utf8');
    } catch {
      this.log(`[drabbit] no save at ${this.filePath} — starting a fresh egg`);
      return { envelope: createFresh(nowMs), outcome: 'fresh-missing' };
    }
    try {
      const envelope = parse(text);
      return { envelope, outcome: 'loaded' };
    } catch (err) {
      const backupPath = path.join(
        path.dirname(this.filePath),
        `drabbit-save.corrupt-${nowMs}.json`,
      );
      try {
        fs.renameSync(this.filePath, backupPath);
      } catch {
        this.log(`[drabbit] WARNING: could not move corrupt save aside (${String(err)})`);
      }
      this.log(
        `[drabbit] save file was corrupt (${err instanceof Error ? err.message : String(err)}); ` +
          `preserved at ${backupPath} and starting a fresh egg`,
      );
      const result: LoadResult = { envelope: createFresh(nowMs), outcome: 'fresh-corrupt' };
      result.backupPath = backupPath;
      return result;
    }
  }

  /** Atomic write: serialize → temp file → rename over the save. */
  save(envelope: SaveEnvelope): void {
    fs.mkdirSync(path.dirname(this.filePath), { recursive: true });
    const tmp = `${this.filePath}.tmp`;
    fs.writeFileSync(tmp, serialize(envelope), 'utf8');
    fs.renameSync(tmp, this.filePath);
  }
}
