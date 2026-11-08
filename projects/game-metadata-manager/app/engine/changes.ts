import type { DatabaseSync } from 'node:sqlite';
import type { ChangeEntry } from '../shared/ipc-contract.js';

type ChangeRow = {
  id: number;
  game_id: string;
  field: string;
  before: string;
  after: string;
  at: string;
};

function rowToEntry(row: ChangeRow): ChangeEntry {
  return {
    id: row.id,
    gameId: row.game_id,
    field: row.field,
    before: row.before,
    after: row.after,
    at: row.at,
  };
}

export class ChangeLog {
  constructor(private db: DatabaseSync) {}

  /** Append a change record. */
  append(gameId: string, field: string, before: string, after: string): ChangeEntry {
    const at = new Date().toISOString();
    const row = this.db
      .prepare(
        'INSERT INTO changes (game_id, field, before, after, at) VALUES (?, ?, ?, ?, ?) RETURNING id'
      )
      .get(gameId, field, before, after, at) as unknown as { id: number } | undefined;
    return { id: row?.id ?? 0, gameId, field, before, after, at };
  }

  listForGame(gameId: string): ChangeEntry[] {
    const rows = this.db
      .prepare('SELECT * FROM changes WHERE game_id = ? ORDER BY id ASC')
      .all(gameId) as unknown as ChangeRow[];
    return rows.map(rowToEntry);
  }

  mostRecent(): ChangeEntry | null {
    const row = this.db
      .prepare('SELECT * FROM changes ORDER BY id DESC LIMIT 1')
      .get() as unknown as ChangeRow | undefined;
    return row ? rowToEntry(row) : null;
  }

  /**
   * Revert the most recent ChangeEntry by restoring the field to `before`.
   * The revert is itself appended to the log (append-only).
   * `restore` writes the field value to the game row.
   */
  undo(restore: (entry: ChangeEntry) => void): { reverted: boolean; gameId?: string } {
    const entry = this.mostRecent();
    if (!entry) return { reverted: false };
    restore(entry);
    this.append(entry.gameId, entry.field, entry.after, entry.before);
    return { reverted: true, gameId: entry.gameId };
  }

  /** Delete all change records (used by bundle-restore wipe path). */
  clear(): void {
    this.db.prepare('DELETE FROM changes').run();
  }
}
