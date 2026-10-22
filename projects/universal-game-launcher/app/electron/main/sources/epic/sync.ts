/**
 * Merge Epic scan results into the library idempotently.
 *
 * Rules (same as Steam):
 * - Match on (source='epic', external_id=appName). Re-scans never duplicate.
 * - Scanner-owned columns (install_dir, launch_uri, launch_capability,
 *   launch_reason) are refreshed from discovery.
 * - User-owned columns (title, favorite, hidden) are NEVER overwritten by
 *   a scan.
 * - Items that vanish from discovery keep their rows and history; their
 *   `missing` flag is computed from install_dir existence at read time.
 */
import type { DatabaseSync } from 'node:sqlite';
import { randomUUID } from 'node:crypto';
import { EPIC_LAUNCHER_URI, type DiscoveredGame } from './adapter';
import { lastScan, recordScan } from '../steam/sync';

export { lastScan, recordScan };

export interface EpicSyncResult {
  added: number;
  updated: number;
  /** Existing epic rows that were not in this scan (kept, history preserved). */
  untouched: number;
}

const LAUNCH_REASON =
  'Per-game Epic launch links are not verified — this opens the Epic Games Launcher.';

export function syncEpicGames(db: DatabaseSync, discovered: DiscoveredGame[]): EpicSyncResult {
  const now = new Date().toISOString();
  let added = 0;
  let updated = 0;

  const findStmt = db.prepare(
    "SELECT id FROM games WHERE source = 'epic' AND external_id = ?",
  );
  const updateStmt = db.prepare(
    `UPDATE games SET install_dir = ?, launch_uri = ?, launch_capability = 'open-client',
       launch_reason = ?, updated_at = ? WHERE id = ?`,
  );
  const insertStmt = db.prepare(
    `INSERT INTO games (id, source, external_id, title, install_dir, launch_uri,
       launch_capability, launch_reason, added_at, updated_at)
     VALUES (?, 'epic', ?, ?, ?, ?, 'open-client', ?, ?, ?)`,
  );

  db.exec('BEGIN');
  try {
    for (const g of discovered) {
      const existing = findStmt.get(g.appName) as { id: string } | undefined;
      if (existing) {
        updateStmt.run(g.installLocation, EPIC_LAUNCHER_URI, LAUNCH_REASON, now, existing.id);
        updated++;
      } else {
        insertStmt.run(
          randomUUID(),
          g.appName,
          g.title,
          g.installLocation,
          EPIC_LAUNCHER_URI,
          LAUNCH_REASON,
          now,
          now,
        );
        added++;
      }
    }
    db.exec('COMMIT');
  } catch (err) {
    db.exec('ROLLBACK');
    throw err;
  }

  const untouchedRow = db
    .prepare(
      `SELECT COUNT(*) AS n FROM games WHERE source = 'epic' AND external_id NOT IN
       (${discovered.map(() => '?').join(',') || "''"})`,
    )
    .get(...discovered.map((g) => g.appName)) as unknown as { n: number };
  return { added, updated, untouched: untouchedRow?.n ?? 0 };
}
