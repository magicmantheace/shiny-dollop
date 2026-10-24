import { existsSync } from 'node:fs';
import type { DatabaseSync } from 'node:sqlite';
import { randomUUID } from 'node:crypto';
import type { Game, Tag, Collection } from '../shared/ipc-contract.js';
import { gameIdFor, type DiscoveredGame } from './scanner.js';

export interface GamePatch {
  title?: string | undefined;
  description?: string | undefined;
  artworkId?: string | null | undefined;
  tagIds?: string[] | undefined;
  collectionIds?: string[] | undefined;
}

type GameRow = {
  id: string;
  title: string;
  original_title: string;
  description: string;
  install_path: string;
  artwork_id: string | null;
  tag_ids: string;
  collection_ids: string;
  created_at: string;
  updated_at: string;
};

function rowToGame(row: GameRow): Game {
  return {
    id: row.id,
    title: row.title,
    originalTitle: row.original_title,
    description: row.description,
    installPath: row.install_path,
    artworkId: row.artwork_id,
    tagIds: JSON.parse(row.tag_ids) as string[],
    collectionIds: JSON.parse(row.collection_ids) as string[],
    missing: false, // computed on demand by rescan, never persisted
    createdAt: row.created_at,
    updatedAt: row.updated_at,
  };
}

export class Library {
  constructor(private db: DatabaseSync) {}

  /** Import discovered executables. Dedupes by game id; never modifies existing rows. */
  importDiscovered(discovered: DiscoveredGame[]): {
    imported: number;
    skipped: number;
    games: Game[];
  } {
    let imported = 0;
    let skipped = 0;
    const games: Game[] = [];

    const insert = this.db.prepare(`
      INSERT INTO games (id, title, original_title, description, install_path, artwork_id, tag_ids, collection_ids, created_at, updated_at)
      VALUES (?, ?, ?, '', ?, NULL, '[]', '[]', ?, ?)
    `);
    const exists = this.db.prepare('SELECT 1 FROM games WHERE id = ?');

    this.db.exec('BEGIN;');
    try {
      const now = new Date().toISOString();
      for (const d of discovered) {
        const id = gameIdFor(d.installPath);
        if (exists.get(id)) {
          skipped++;
          continue;
        }
        insert.run(id, d.title, d.originalTitle, d.installPath, now, now);
        imported++;
        games.push({
          id,
          title: d.title,
          originalTitle: d.originalTitle,
          description: '',
          installPath: d.installPath,
          artworkId: null,
          tagIds: [],
          collectionIds: [],
          missing: false,
          createdAt: now,
          updatedAt: now,
        });
      }
      this.db.exec('COMMIT;');
    } catch (err) {
      this.db.exec('ROLLBACK;');
      throw err;
    }
    return { imported, skipped, games };
  }

  list(): Game[] {
    const rows = this.db
      .prepare('SELECT * FROM games ORDER BY title COLLATE NOCASE')
      .all() as unknown as GameRow[];
    return rows.map(rowToGame);
  }

  get(gameId: string): Game | null {
    const row = this.db
      .prepare('SELECT * FROM games WHERE id = ?')
      .get(gameId) as unknown as GameRow | undefined;
    return row ? rowToGame(row) : null;
  }

  /**
   * Recompute `missing` for every game via fs.existsSync.
   * Never deletes anything — missing rows are flagged, not removed.
   */
  rescan(): { missingIds: string[] } {
    const rows = this.db.prepare('SELECT id, install_path FROM games').all() as unknown as Array<{
      id: string;
      install_path: string;
    }>;
    const missingIds = rows
      .filter((r) => !existsSync(r.install_path))
      .map((r) => r.id);
    return { missingIds };
  }

  /**
   * Apply a validated patch. Records one ChangeEntry per changed field
   * (before/after as strings; arrays JSON-encoded) and bumps updatedAt.
   */
  update(gameId: string, patch: GamePatch): Game {
    const current = this.get(gameId);
    if (!current) throw new Error(`game not found: ${gameId}`);

    const updates: {
      title: string;
      description: string;
      artworkId: string | null;
      tagIds: string;
      collectionIds: string;
    } = {
      title: patch.title ?? current.title,
      description: patch.description ?? current.description,
      artworkId: patch.artworkId === undefined ? current.artworkId : patch.artworkId,
      tagIds: JSON.stringify(patch.tagIds ?? current.tagIds),
      collectionIds: JSON.stringify(patch.collectionIds ?? current.collectionIds),
    };

    const changes: Array<{ field: string; before: string; after: string }> = [];
    const beforeStr: Record<'title' | 'description' | 'artworkId' | 'tagIds' | 'collectionIds', string> = {
      title: current.title,
      description: current.description,
      artworkId: JSON.stringify(current.artworkId),
      tagIds: JSON.stringify(current.tagIds),
      collectionIds: JSON.stringify(current.collectionIds),
    };
    const afterStr: Record<'title' | 'description' | 'artworkId' | 'tagIds' | 'collectionIds', string> = {
      title: updates.title,
      description: updates.description,
      artworkId: JSON.stringify(updates.artworkId),
      tagIds: updates.tagIds,
      collectionIds: updates.collectionIds,
    };
    for (const field of ['title', 'description', 'artworkId', 'tagIds', 'collectionIds'] as const) {
      const before = beforeStr[field];
      const after = afterStr[field];
      if (before !== after) changes.push({ field, before, after });
    }

    if (changes.length === 0) return current;

    const now = new Date().toISOString();
    this.db.exec('BEGIN;');
    try {
      this.db
        .prepare(
          `UPDATE games SET title = ?, description = ?, artwork_id = ?, tag_ids = ?, collection_ids = ?, updated_at = ? WHERE id = ?`
        )
        .run(
          updates.title,
          updates.description,
          updates.artworkId,
          updates.tagIds,
          updates.collectionIds,
          now,
          gameId
        );
      const log = this.db.prepare(
        'INSERT INTO changes (game_id, field, before, after, at) VALUES (?, ?, ?, ?, ?)'
      );
      for (const c of changes) log.run(gameId, c.field, c.before, c.after, now);
      this.db.exec('COMMIT;');
    } catch (err) {
      this.db.exec('ROLLBACK;');
      throw err;
    }

    const next = this.get(gameId);
    if (!next) throw new Error(`game vanished after update: ${gameId}`);
    return next;
  }

  /** Set a game field directly (used by undo and bundle import). */
  setField(gameId: string, field: string, value: string): void {
    const column =
      field === 'title'
        ? 'title'
        : field === 'description'
          ? 'description'
          : field === 'artworkId'
            ? 'artwork_id'
            : field === 'tagIds'
              ? 'tag_ids'
              : field === 'collectionIds'
                ? 'collection_ids'
                : null;
    if (!column) throw new Error(`unsupported field for setField: ${field}`);
    this.db
      .prepare(`UPDATE games SET ${column} = ?, updated_at = ? WHERE id = ?`)
      .run(value, new Date().toISOString(), gameId);
  }

  /**
   * Insert a game wholesale (used by bundle import). Upserts: if the id
   * already exists the row is replaced only via the merge path's update().
   */
  insertGame(game: Game): void {
    this.db
      .prepare(
        `INSERT OR REPLACE INTO games (id, title, original_title, description, install_path, artwork_id, tag_ids, collection_ids, created_at, updated_at)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`
      )
      .run(
        game.id,
        game.title,
        game.originalTitle,
        game.description,
        game.installPath,
        game.artworkId,
        JSON.stringify(game.tagIds),
        JSON.stringify(game.collectionIds),
        game.createdAt,
        game.updatedAt
      );
  }

  removeGame(gameId: string): void {
    this.db.prepare('DELETE FROM games WHERE id = ?').run(gameId);
  }

  /** Set the artwork id (nullable), used by bundle merge. */
  setArtworkId(gameId: string, artworkId: string | null): void {
    this.db
      .prepare('UPDATE games SET artwork_id = ?, updated_at = ? WHERE id = ?')
      .run(artworkId, new Date().toISOString(), gameId);
  }

  // ---- tags ----

  listTags(): Tag[] {
    const rows = this.db.prepare('SELECT * FROM tags ORDER BY name COLLATE NOCASE').all() as unknown as Tag[];
    return rows;
  }

  addTag(name: string): Tag {
    const trimmed = name.trim();
    if (!trimmed) throw new Error('tag name must not be empty');
    const id = randomUUID();
    try {
      this.db.prepare('INSERT INTO tags (id, name) VALUES (?, ?)').run(id, trimmed);
    } catch (err) {
      const existing = this.db
        .prepare('SELECT * FROM tags WHERE name = ?')
        .get(trimmed) as unknown as Tag | undefined;
      if (existing) return existing;
      throw err;
    }
    return { id, name: trimmed };
  }

  removeTag(id: string): void {
    this.db.exec('BEGIN;');
    try {
      this.db.prepare('DELETE FROM tags WHERE id = ?').run(id);
      // Detach from games rather than deleting games.
      const games = this.db.prepare('SELECT id, tag_ids FROM games').all() as unknown as Array<{
        id: string;
        tag_ids: string;
      }>;
      const upd = this.db.prepare('UPDATE games SET tag_ids = ? WHERE id = ?');
      for (const g of games) {
        const ids = (JSON.parse(g.tag_ids) as string[]).filter((t) => t !== id);
        upd.run(JSON.stringify(ids), g.id);
      }
      this.db.exec('COMMIT;');
    } catch (err) {
      this.db.exec('ROLLBACK;');
      throw err;
    }
  }

  upsertTag(tag: Tag): void {
    this.db
      .prepare('INSERT OR IGNORE INTO tags (id, name) VALUES (?, ?)')
      .run(tag.id, tag.name);
  }

  // ---- collections ----

  listCollections(): Collection[] {
    const rows = this.db.prepare('SELECT * FROM collections ORDER BY name COLLATE NOCASE').all() as unknown as Collection[];
    return rows;
  }

  addCollection(name: string): Collection {
    const trimmed = name.trim();
    if (!trimmed) throw new Error('collection name must not be empty');
    const id = randomUUID();
    try {
      this.db.prepare('INSERT INTO collections (id, name) VALUES (?, ?)').run(id, trimmed);
    } catch (err) {
      const existing = this.db
        .prepare('SELECT * FROM collections WHERE name = ?')
        .get(trimmed) as unknown as Collection | undefined;
      if (existing) return existing;
      throw err;
    }
    return { id, name: trimmed };
  }

  removeCollection(id: string): void {
    this.db.exec('BEGIN;');
    try {
      this.db.prepare('DELETE FROM collections WHERE id = ?').run(id);
      const games = this.db.prepare('SELECT id, collection_ids FROM games').all() as unknown as Array<{
        id: string;
        collection_ids: string;
      }>;
      const upd = this.db.prepare('UPDATE games SET collection_ids = ? WHERE id = ?');
      for (const g of games) {
        const ids = (JSON.parse(g.collection_ids) as string[]).filter((c) => c !== id);
        upd.run(JSON.stringify(ids), g.id);
      }
      this.db.exec('COMMIT;');
    } catch (err) {
      this.db.exec('ROLLBACK;');
      throw err;
    }
  }

  upsertCollection(collection: Collection): void {
    this.db
      .prepare('INSERT OR IGNORE INTO collections (id, name) VALUES (?, ?)')
      .run(collection.id, collection.name);
  }
}
