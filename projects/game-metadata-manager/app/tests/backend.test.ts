import { describe, expect, it } from 'vitest';
import { mkdtempSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { makeContext, makeGame, minimalPng, firstGame } from './helpers.js';
import type { Game, MetadataBundle } from '../shared/ipc-contract.js';

describe('Library', () => {
  it('importDiscovered dedupes by id and never modifies existing rows', () => {
    const ctx = makeContext();
    try {
      const d = { installPath: 'C:/Games/Halo/halo.exe', title: 'halo', originalTitle: 'halo' };
      const first = ctx.library.importDiscovered([d]);
      expect(first.imported).toBe(1);
      expect(first.skipped).toBe(0);
      const second = ctx.library.importDiscovered([d]);
      expect(second.imported).toBe(0);
      expect(second.skipped).toBe(1);
      expect(ctx.library.list()).toHaveLength(1);
    } finally {
      ctx.dispose();
    }
  });

  it('update records one ChangeEntry per changed field with before/after', () => {
    const ctx = makeContext();
    try {
      const g = firstGame(ctx.library.importDiscovered([
        { installPath: 'C:/Games/A/a.exe', title: 'a', originalTitle: 'a' },
      ]).games);
      const updated = ctx.library.update(g.id, {
        title: 'Renamed',
        description: 'New desc',
      });
      expect(updated.title).toBe('Renamed');
      const entries = ctx.changes.listForGame(g.id);
      expect(entries.map((e) => e.field).sort()).toEqual(['description', 'title']);
      const titleChange = entries.find((e) => e.field === 'title');
      expect(titleChange?.before).toBe('a');
      expect(titleChange?.after).toBe('Renamed');
    } finally {
      ctx.dispose();
    }
  });

  it('update with no actual changes records nothing', () => {
    const ctx = makeContext();
    try {
      const g = firstGame(ctx.library.importDiscovered([
        { installPath: 'C:/Games/A/a.exe', title: 'a', originalTitle: 'a' },
      ]).games);
      ctx.library.update(g.id, { title: 'a' });
      expect(ctx.changes.listForGame(g.id)).toHaveLength(0);
    } finally {
      ctx.dispose();
    }
  });

  it('rescan marks missing exes without deleting anything', () => {
    const root = mkdtempSync(join(tmpdir(), 'gmm-missing-'));
    const ctx = makeContext();
    try {
      const exePath = join(root, 'game.exe');
      writeFileSync(exePath, 'MZ');
      const g = firstGame(ctx.library.importDiscovered([
        { installPath: exePath, title: 'game', originalTitle: 'game' },
      ]).games);

      expect(ctx.library.rescan().missingIds).toEqual([]);

      rmSync(exePath);
      const { missingIds } = ctx.library.rescan();
      expect(missingIds).toEqual([g.id]);
      // Nothing deleted — the row survives.
      expect(ctx.library.list()).toHaveLength(1);
      expect(ctx.library.get(g.id)?.installPath).toBe(exePath);
    } finally {
      ctx.dispose();
      rmSync(root, { recursive: true, force: true });
    }
  });

  it('removeTag detaches the tag from games instead of deleting games', () => {
    const ctx = makeContext();
    try {
      const tag = ctx.library.addTag('rpg');
      const g = firstGame(ctx.library.importDiscovered([
        { installPath: 'C:/Games/A/a.exe', title: 'a', originalTitle: 'a' },
      ]).games);
      ctx.library.update(g.id, { tagIds: [tag.id] });
      ctx.library.removeTag(tag.id);
      expect(ctx.library.listTags()).toHaveLength(0);
      expect(ctx.library.get(g.id)?.tagIds).toEqual([]);
    } finally {
      ctx.dispose();
    }
  });

  it('removeTag advances updatedAt only for games that had the tag, and a pre-deletion snapshot cannot restore it', () => {
    const ctx = makeContext();
    try {
      const tag = ctx.library.addTag('rpg');
      const old = '2025-01-01T00:00:00.000Z';
      const assigned = makeGame({ id: 'g-tag-assigned', installPath: 'C:/Games/Assigned/game.exe', tagIds: [tag.id], createdAt: old, updatedAt: old });
      const unassigned = makeGame({ id: 'g-tag-unassigned', installPath: 'C:/Games/Unassigned/game.exe', tagIds: [], createdAt: old, updatedAt: old });
      ctx.library.insertGame(assigned);
      ctx.library.insertGame(unassigned);

      ctx.library.removeTag(tag.id);

      const afterAssigned = ctx.library.get(assigned.id);
      expect(afterAssigned?.tagIds).toEqual([]);
      expect(afterAssigned!.updatedAt > old).toBe(true);
      // Games whose assignments did not change are not modified.
      expect(ctx.library.get(unassigned.id)?.updatedAt).toBe(old);

      // A bundle snapshot taken before the deletion carries the older
      // updatedAt, so its (still-assigned) tagIds must lose the merge.
      const snapshot: MetadataBundle = {
        formatVersion: '1.0.0',
        exportedAt: old,
        exporter: 'game-metadata-manager/1.0.0',
        games: [{ ...assigned }],
        artwork: [],
      };
      const res = ctx.bundles.importBundle(JSON.stringify(snapshot));
      expect(res.updated).toBe(0);
      expect(ctx.library.get(assigned.id)?.tagIds).toEqual([]);
    } finally {
      ctx.dispose();
    }
  });

  it('removeCollection advances updatedAt only for games that had the collection, and a pre-deletion snapshot cannot restore it', () => {
    const ctx = makeContext();
    try {
      const col = ctx.library.addCollection('favorites');
      const old = '2025-01-01T00:00:00.000Z';
      const assigned = makeGame({
        id: 'g-col-assigned',
        collectionIds: [col.id],
        installPath: 'C:/Games/AssignedCol/game.exe',
        createdAt: old,
        updatedAt: old,
      });
      const unassigned = makeGame({ id: 'g-col-unassigned', installPath: 'C:/Games/UnassignedCol/game.exe', collectionIds: [], createdAt: old, updatedAt: old });
      ctx.library.insertGame(assigned);
      ctx.library.insertGame(unassigned);

      ctx.library.removeCollection(col.id);

      const afterAssigned = ctx.library.get(assigned.id);
      expect(afterAssigned?.collectionIds).toEqual([]);
      expect(afterAssigned!.updatedAt > old).toBe(true);
      expect(ctx.library.get(unassigned.id)?.updatedAt).toBe(old);

      const snapshot: MetadataBundle = {
        formatVersion: '1.0.0',
        exportedAt: old,
        exporter: 'game-metadata-manager/1.0.0',
        games: [{ ...assigned }],
        artwork: [],
      };
      const res = ctx.bundles.importBundle(JSON.stringify(snapshot));
      expect(res.updated).toBe(0);
      expect(ctx.library.get(assigned.id)?.collectionIds).toEqual([]);
    } finally {
      ctx.dispose();
    }
  });

  it('insertGame rejects an install-path collision with a different game id instead of replacing the local game', () => {
    const ctx = makeContext();
    try {
      const local = makeGame({
        id: 'g-local',
        title: 'Locally Edited',
        installPath: 'C:/Games/Shared/game.exe',
        updatedAt: '2025-06-01T00:00:00.000Z',
      });
      ctx.library.insertGame(local);
      const incoming = makeGame({
        id: 'g-incoming',
        title: 'Incoming',
        installPath: 'C:/Games/Shared/game.exe',
        updatedAt: '2025-01-01T00:00:00.000Z',
      });
      expect(() => ctx.library.insertGame(incoming)).toThrow(/install path collision/);
      expect(ctx.library.get('g-local')?.title).toBe('Locally Edited');
      expect(ctx.library.get('g-incoming')).toBeNull();
      expect(ctx.library.list()).toHaveLength(1);
    } finally {
      ctx.dispose();
    }
  });

  it('addTag returns the existing tag on duplicate names', () => {
    const ctx = makeContext();
    try {
      const a = ctx.library.addTag('rpg');
      const b = ctx.library.addTag('rpg');
      expect(a.id).toBe(b.id);
    } finally {
      ctx.dispose();
    }
  });
});

describe('ChangeLog undo', () => {
  it('undo reverts the most recent change and returns the game id', () => {
    const ctx = makeContext();
    try {
      const g = firstGame(ctx.library.importDiscovered([
        { installPath: 'C:/Games/A/a.exe', title: 'a', originalTitle: 'a' },
      ]).games);
      ctx.library.update(g.id, { title: 'Renamed' });
      const res = ctx.changes.undo((entry) => ctx.library.setField(entry.gameId, entry.field, entry.before));
      expect(res.reverted).toBe(true);
      expect(res.gameId).toBe(g.id);
      expect(ctx.library.get(g.id)?.title).toBe('a');
    } finally {
      ctx.dispose();
    }
  });

  it('undo on an empty log reports not reverted', () => {
    const ctx = makeContext();
    try {
      const res = ctx.changes.undo(() => {
        throw new Error('should not run');
      });
      expect(res.reverted).toBe(false);
    } finally {
      ctx.dispose();
    }
  });
});

describe('BundleIO', () => {
  function seed(ctx: ReturnType<typeof makeContext>): { game: Game; artId: string } {
    const tag = ctx.library.addTag('shooter');
    const col = ctx.library.addCollection('favorites');
    const png = join(ctx.dir, 'cover.png');
    writeFileSync(png, minimalPng());
    const art = ctx.artwork.add(png, 'file');
    const g = firstGame(ctx.library.importDiscovered([
      { installPath: 'C:/Games/Halo/halo.exe', title: 'halo', originalTitle: 'halo' },
    ]).games);
    const game = ctx.library.update(g.id, {
      title: 'Halo Deluxe',
      description: 'Sci-fi shooter',
      artworkId: art.id,
      tagIds: [tag.id],
      collectionIds: [col.id],
    });
    return { game, artId: art.id };
  }

  it('export → wipe → import restores everything identically', () => {
    const ctx = makeContext();
    try {
      const { game } = seed(ctx);
      const json = ctx.bundles.exportBundle();
      const bundle = JSON.parse(json) as MetadataBundle;
      expect(bundle.formatVersion).toBe('1.0.0');
      expect(bundle.exporter).toBe('game-metadata-manager/1.0.0');
      expect(bundle.games).toHaveLength(1);
      expect(bundle.artwork).toHaveLength(1);

      ctx.bundles.wipe();
      expect(ctx.library.list()).toHaveLength(0);
      expect(ctx.artwork.list()).toHaveLength(0);

      const res = ctx.bundles.importBundle(json);
      expect(res.added).toBe(1);
      expect(res.updated).toBe(0);

      const restored = ctx.library.get(game.id);
      expect(restored).toMatchObject({
        title: 'Halo Deluxe',
        description: 'Sci-fi shooter',
        artworkId: game.artworkId,
        tagIds: game.tagIds,
        collectionIds: game.collectionIds,
      });
      expect(ctx.library.listTags().map((t) => t.name)).toContain('shooter');
      expect(ctx.library.listCollections().map((c) => c.name)).toContain('favorites');
      expect(ctx.artwork.list()).toHaveLength(1);
      expect(ctx.artwork.fileUrl(game.artworkId!)).toMatch(/^file:\/\//);
    } finally {
      ctx.dispose();
    }
  });

  it('conflict merge: newer bundle wins and conflicts are listed', () => {
    const ctx = makeContext();
    try {
      const { game } = seed(ctx);
      // Local edit is newer than the exported bundle.
      const localNow = ctx.library.update(game.id, { title: 'Local Name' });

      // Build a bundle payload with an OLDER updatedAt and a different title.
      const bundle: MetadataBundle = {
        formatVersion: '1.0.0',
        exportedAt: new Date().toISOString(),
        exporter: 'game-metadata-manager/1.0.0',
        games: [
          {
            ...localNow,
            title: 'Bundle Name',
            updatedAt: new Date(Date.now() - 1000 * 60 * 60).toISOString(), // 1h older
          },
        ],
        artwork: [],
      };
      const res = ctx.bundles.importBundle(JSON.stringify(bundle));
      // Local is newer so nothing changes, but the divergence is still recorded.
      expect(res.updated).toBe(0);
      const conflict = res.conflicts.find((c) => c.field === 'title');
      expect(conflict).toMatchObject({ chosen: 'local' });
      expect(conflict?.localValue).toContain('Local Name');
      expect(conflict?.bundleValue).toContain('Bundle Name');
      expect(ctx.library.get(game.id)?.title).toBe('Local Name');

      // Now a NEWER bundle wins.
      const newer: MetadataBundle = {
        formatVersion: '1.0.0',
        exportedAt: new Date().toISOString(),
        exporter: 'game-metadata-manager/1.0.0',
        games: [
          {
            ...localNow,
            title: 'Bundle Name 2',
            updatedAt: new Date(Date.now() + 1000 * 60 * 60).toISOString(), // 1h newer
          },
        ],
        artwork: [],
      };
      const res2 = ctx.bundles.importBundle(JSON.stringify(newer));
      expect(res2.updated).toBe(1); // bundle won → a change was applied
      const conflict2 = res2.conflicts.find((c) => c.field === 'title');
      expect(conflict2?.chosen).toBe('bundle');
      expect(ctx.library.get(game.id)?.title).toBe('Bundle Name 2');
    } finally {
      ctx.dispose();
    }
  });

  it('preserves the winning bundle updatedAt for setField merges and keeps chronological ordering', () => {
    const ctx = makeContext();
    try {
      const local = makeGame({
        id: 'g-chrono',
        title: 'January Title',
        description: 'January desc',
        createdAt: '2025-01-01T00:00:00.000Z',
        updatedAt: '2025-01-01T00:00:00.000Z',
      });
      ctx.library.insertGame(local);

      const feb: MetadataBundle = {
        formatVersion: '1.0.0',
        exportedAt: '2025-02-01T00:00:00.000Z',
        exporter: 'game-metadata-manager/1.0.0',
        games: [
          { ...local, title: 'February Title', description: 'February desc', updatedAt: '2025-02-01T00:00:00.000Z' },
        ],
        artwork: [],
      };
      ctx.bundles.importBundle(JSON.stringify(feb));
      const afterFeb = ctx.library.get(local.id);
      expect(afterFeb?.title).toBe('February Title');
      // The winning source timestamp must be preserved, not replaced by import time.
      expect(afterFeb?.updatedAt).toBe('2025-02-01T00:00:00.000Z');

      // A genuinely newer (March) snapshot must still win after the February import.
      const mar: MetadataBundle = {
        ...feb,
        exportedAt: '2025-03-01T00:00:00.000Z',
        games: [
          { ...local, title: 'March Title', description: 'March desc', updatedAt: '2025-03-01T00:00:00.000Z' },
        ],
      };
      const res = ctx.bundles.importBundle(JSON.stringify(mar));
      expect(res.updated).toBe(1);
      const afterMar = ctx.library.get(local.id);
      expect(afterMar?.title).toBe('March Title');
      expect(afterMar?.updatedAt).toBe('2025-03-01T00:00:00.000Z');
    } finally {
      ctx.dispose();
    }
  });

  it('preserves the winning bundle updatedAt for artworkId merges (setArtworkId path)', () => {
    const ctx = makeContext();
    try {
      const local = makeGame({
        id: 'g-art-chrono',
        artworkId: null,
        createdAt: '2025-01-01T00:00:00.000Z',
        updatedAt: '2025-01-01T00:00:00.000Z',
      });
      ctx.library.insertGame(local);

      const feb: MetadataBundle = {
        formatVersion: '1.0.0',
        exportedAt: '2025-02-01T00:00:00.000Z',
        exporter: 'game-metadata-manager/1.0.0',
        games: [{ ...local, artworkId: 'art-feb', updatedAt: '2025-02-01T00:00:00.000Z' }],
        artwork: [],
      };
      ctx.bundles.importBundle(JSON.stringify(feb));
      const afterFeb = ctx.library.get(local.id);
      expect(afterFeb?.artworkId).toBe('art-feb');
      expect(afterFeb?.updatedAt).toBe('2025-02-01T00:00:00.000Z');

      const mar: MetadataBundle = {
        ...feb,
        exportedAt: '2025-03-01T00:00:00.000Z',
        games: [{ ...local, artworkId: 'art-mar', updatedAt: '2025-03-01T00:00:00.000Z' }],
      };
      ctx.bundles.importBundle(JSON.stringify(mar));
      const afterMar = ctx.library.get(local.id);
      expect(afterMar?.artworkId).toBe('art-mar');
      expect(afterMar?.updatedAt).toBe('2025-03-01T00:00:00.000Z');
    } finally {
      ctx.dispose();
    }
  });

  it('records ChangeEntry records for bundle-sourced changes', () => {
    const ctx = makeContext();
    try {
      const { game } = seed(ctx);
      const bundle: MetadataBundle = {
        formatVersion: '1.0.0',
        exportedAt: new Date().toISOString(),
        exporter: 'game-metadata-manager/1.0.0',
        games: [
          {
            ...game,
            description: 'Bundle description',
            updatedAt: new Date(Date.now() + 1000).toISOString(),
          },
        ],
        artwork: [],
      };
      ctx.bundles.importBundle(JSON.stringify(bundle));
      const entries = ctx.changes.listForGame(game.id);
      // The bundle import JSON-encodes values in its change records.
      const desc = entries.find((e) => e.field === 'description' && e.after === '"Bundle description"');
      expect(desc).toBeDefined();
      expect(desc?.before).toBe('"Sci-fi shooter"');
    } finally {
      ctx.dispose();
    }
  });

  it('rejects unknown major versions and malformed versions', () => {
    const ctx = makeContext();
    try {
      expect(() => ctx.bundles.importBundle(JSON.stringify({ formatVersion: '2.0.0', games: [], artwork: [] }))).toThrow(
        /unsupported bundle formatVersion/
      );
      expect(() => ctx.bundles.importBundle(JSON.stringify({ formatVersion: '1.0', games: [], artwork: [] }))).toThrow(
        /not valid semver/
      );
      expect(() => ctx.bundles.importBundle(JSON.stringify({ games: [], artwork: [] }))).toThrow(
        /missing formatVersion/
      );
      expect(() => ctx.bundles.importBundle('not json')).toThrow(/not valid JSON/);
    } finally {
      ctx.dispose();
    }
  });

  it('accepts a newer minor/patch version', () => {
    const ctx = makeContext();
    try {
      const res = ctx.bundles.importBundle(
        JSON.stringify({ formatVersion: '1.2.3', games: [], artwork: [] })
      );
      expect(res.added).toBe(0);
    } finally {
      ctx.dispose();
    }
  });

  it('bundle import rejects an install-path collision and leaves the local game intact', () => {
    const ctx = makeContext();
    try {
      const local = makeGame({
        id: 'g-local2',
        title: 'Locally Edited',
        installPath: 'C:/Games/Shared2/game.exe',
        updatedAt: '2025-06-01T00:00:00.000Z',
      });
      ctx.library.insertGame(local);
      const bundle: MetadataBundle = {
        formatVersion: '1.0.0',
        exportedAt: '2025-01-01T00:00:00.000Z',
        exporter: 'game-metadata-manager/1.0.0',
        games: [
          makeGame({
            id: 'g-incoming2',
            title: 'Older Incoming',
            installPath: 'C:/Games/Shared2/game.exe',
            createdAt: '2025-01-01T00:00:00.000Z',
            updatedAt: '2025-01-01T00:00:00.000Z',
          }),
        ],
        artwork: [],
      };
      expect(() => ctx.bundles.importBundle(JSON.stringify(bundle))).toThrow(/install path collision/);
      expect(ctx.library.get('g-local2')?.title).toBe('Locally Edited');
      expect(ctx.library.get('g-incoming2')).toBeNull();
    } finally {
      ctx.dispose();
    }
  });

  it('rolls back all bundle mutations when artwork restoration fails', () => {
    const ctx = makeContext();
    try {
      const cacheDir = join(ctx.dir, 'artwork-cache');
      // Sabotage the artwork cache: replace its directory with a file
      // so writing restored artwork must throw.
      rmSync(cacheDir, { recursive: true, force: true });
      writeFileSync(cacheDir, 'not a directory');

      const game = makeGame({ id: 'g-rollback', installPath: 'C:/Games/Rollback/game.exe' });
      const bundle: MetadataBundle = {
        formatVersion: '1.0.0',
        exportedAt: new Date().toISOString(),
        exporter: 'game-metadata-manager/1.0.0',
        games: [game],
        artwork: [
          { id: 'art-rollback', provenance: 'bundle', mime: 'image/png', dataBase64: minimalPng().toString('base64') },
        ],
      };
      expect(() => ctx.bundles.importBundle(JSON.stringify(bundle))).toThrow();
      // Nothing from the failed import may persist.
      expect(ctx.library.get('g-rollback')).toBeNull();
      expect(ctx.library.list()).toHaveLength(0);
      expect(ctx.changes.listForGame('g-rollback')).toHaveLength(0);
      expect(ctx.changes.mostRecent()).toBeNull();
      expect(ctx.artwork.list()).toHaveLength(0);
    } finally {
      ctx.dispose();
    }
  });

  it('rejects bundles over the 50 MB guard', () => {
    const ctx = makeContext();
    try {
      expect(() =>
        ctx.bundles.importBundle(
          JSON.stringify({ formatVersion: '1.0.0', games: [], artwork: [] }).padEnd(50 * 1024 * 1024 + 10, 'x')
        )
      ).toThrow(/50 MB/);
    } finally {
      ctx.dispose();
    }
  });
});
