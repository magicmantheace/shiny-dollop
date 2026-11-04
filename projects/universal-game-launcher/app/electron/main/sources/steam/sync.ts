/**
 * Merge Steam scan results into the library idempotently.
 *
 * Rules:
 * - Match on (source='steam', external_id=appid). Re-scans never duplicate.
 * - Scanner-owned columns (install_dir, launch_uri, launch_capability,
 *   launch_reason) are refreshed from discovery.
 * - User-owned columns (title, favorite, hidden) are NEVER overwritten by
 *   a scan — a renamed manifest or re-scan preserves the user's edits.
 * - Games that vanish from discovery keep their rows and history; their
 *   `missing` flag is computed from install_dir existence at read time.
 */
import type { DatabaseSync } from 'node:sqlite';
import { randomUUID } from 'node:crypto';
import type { DiscoveredGame } from './adapter';
import { buildRunGameUri } from './adapter';

export interface SteamSyncResult {
  added: number;
  updated: number;
  /** Existing steam rows that were not in this scan (kept, history preserved). */
  untouched: number;
}

export function syncSteamGames(db: DatabaseSync, discovered: DiscoveredGame[]): SteamSyncResult {
  const now = new Date().toISOString();
  let added = 0;
  let updated = 0;

  const findStmt = db.prepare(
    "SELECT id FROM games WHERE source = 'steam' AND external_id = ?",
  );
  const updateStmt = db.prepare(
    `UPDATE games SET install_dir = ?, launch_uri = ?, launch_capability = 'native-uri',
       launch_reason = ?, updated_at = ? WHERE id = ?`,
  );
  const insertStmt = db.prepare(
    `INSERT INTO games (id, source, external_id, title, install_dir, launch_uri,
       launch_capability, launch_reason, added_at, updated_at)
     VALUES (?, 'steam', ?, ?, ?, ?, 'native-uri', ?, ?, ?)`,
  );

  db.exec('BEGIN');
  try {
    for (const g of discovered) {
      const uri = buildRunGameUri(g.appid);
      const reason =
        'Launches through the installed Steam client via its documented rungameid protocol.';
      const existing = findStmt.get(g.appid) as { id: string } | undefined;
      if (existing) {
        updateStmt.run(g.installDir, uri, reason, now, existing.id);
        updated++;
      } else {
        insertStmt.run(randomUUID(), g.appid, g.title, g.installDir, uri, reason, now, now);
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
      `SELECT COUNT(*) AS n FROM games WHERE source = 'steam' AND external_id NOT IN
       (${discovered.map(() => '?').join(',') || "''"})`,
    )
    .get(...discovered.map((g) => g.appid)) as unknown as { n: number };
  return { added, updated, untouched: untouchedRow?.n ?? 0 };
}

/** Record a scan run in scan_log for the Settings UI. */
export function recordScan(
  db: DatabaseSync,
  source: string,
  status: 'ok' | 'failed' | 'cancelled',
  gamesFound: number,
  error: string | null,
): void {
  db.prepare(
    `INSERT INTO scan_log (source, scanned_at, status, games_found, error)
     VALUES (?, ?, ?, ?, ?)`,
  ).run(source, new Date().toISOString(), status, gamesFound, error);
}

/** Latest scan_log entry per source, for sources.status. */
export function lastScan(db: DatabaseSync, source: string): {
  scannedAt: string | null;
  status: string | null;
  gamesFound: number;
  error: string | null;
} {
  const row = db
    .prepare(
      `SELECT scanned_at, status, games_found, error FROM scan_log
       WHERE source = ? ORDER BY id DESC LIMIT 1`,
    )
    .get(source) as
    | { scanned_at: string; status: string; games_found: number; error: string | null }
    | undefined;
  if (!row) return { scannedAt: null, status: null, gamesFound: 0, error: null };
  return {
    scannedAt: row.scanned_at,
    status: row.status,
    gamesFound: row.games_found,
    error: row.error,
  };
}
