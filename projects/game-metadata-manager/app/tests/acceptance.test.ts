/**
 * MVP acceptance walkthrough (recorded 2026-10-23, Linux VM, Node 24).
 *
 * Exercises the FULL MVP workflow against the real engine (no mocks):
 *   1. import a fixture library (3 fake games)
 *   2. edit title / description / tags, add artwork with provenance, assign it
 *   3. detect a missing install path (without deleting anything)
 *   4. export a versioned metadata bundle, wipe, re-import, verify identical
 */
import { existsSync, mkdirSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import { scanRoots } from '../engine/scanner.js';
import { makeContext, minimalPng } from './helpers.js';

function buildFixtureLibrary(): string {
  const root = join(tmpdir(), `gmm-accept-${Date.now()}`);
  const gamesDir = join(root, 'Games');
  mkdirSync(gamesDir, { recursive: true });
  for (const name of ['Nebula_Drift.exe', 'Cinderfall.exe', 'Pixel_Pioneers.exe']) {
    writeFileSync(join(gamesDir, name), Buffer.from('MZ fake exe'));
  }
  return root;
}

describe('MVP acceptance walkthrough', () => {
  it('import -> edit -> missing detection -> reversible bundle export', () => {
    const fixtureRoot = buildFixtureLibrary();
    try {
      const ctx = makeContext();
      try {
        // 1. Import a fixture library.
        const discovered = scanRoots([join(fixtureRoot, 'Games')]);
        const { imported, skipped } = ctx.library.importDiscovered(discovered);
        expect(imported).toBe(3);
        expect(skipped).toBe(0);
        const games = ctx.library.list();
        expect(games).toHaveLength(3);

        // 2. Edit title / description / tags; add artwork with provenance.
        const target = games.find((g) => g.title === 'Nebula Drift');
        expect(target).toBeDefined();
        const tag = ctx.library.addTag('space-opera');
        const col = ctx.library.addCollection('Backlog');
        const updated = ctx.library.update(target!.id, {
          title: 'Nebula Drift — Remastered',
          description: 'A fictional space hauler, catalogued for testing.',
          tagIds: [tag.id],
          collectionIds: [col.id],
        });
        expect(updated.title).toBe('Nebula Drift — Remastered');
        expect(updated.tagIds).toContain(tag.id);
        const pngPath = join(fixtureRoot, 'cover.png');
        writeFileSync(pngPath, minimalPng());
        const art = ctx.artwork.add(pngPath, 'hand-drawn test cover');
        expect(art.provenance).toBe('hand-drawn test cover');
        const withArt = ctx.library.update(target!.id, { artworkId: art.id });
        expect(withArt.artworkId).toBe(art.id);
        // Edits are journaled (undoable).
        expect(ctx.changes.listForGame(target!.id).length).toBeGreaterThan(0);

        // 3. Detect a missing install path — the engine flags it via rescan
        // (missing is computed on demand, never persisted); nothing is deleted.
        rmSync(join(fixtureRoot, 'Games', 'Cinderfall.exe'));
        const { missingIds } = ctx.library.rescan();
        expect(missingIds).toHaveLength(1);
        const stillListed = ctx.library.list();
        expect(stillListed).toHaveLength(3);
        const missingGame = stillListed.find((g) => g.id === missingIds[0])!;
        expect(missingGame.title).toBe('Cinderfall');
        expect(existsSync(missingGame.installPath)).toBe(false);

        // 4. Export a versioned bundle, wipe, re-import — everything restores.
        const json = ctx.bundles.exportBundle();
        const parsed = JSON.parse(json) as { formatVersion: string };
        expect(parsed.formatVersion).toBe('1.0.0');
        const fresh = makeContext();
        try {
          const result = fresh.bundles.importBundle(json);
          expect(result.added).toBe(3);
          expect(result.conflicts).toHaveLength(0);
          const restored = fresh.library.list();
          expect(restored).toHaveLength(3);
          const restoredTarget = restored.find((g) => g.id === target!.id)!;
          expect(restoredTarget.title).toBe('Nebula Drift — Remastered');
          expect(restoredTarget.description).toContain('fictional space hauler');
          expect(restoredTarget.tagIds).toContain(tag.id);
          expect(fresh.library.listTags().map((t) => t.name)).toContain('space-opera');
          expect(fresh.library.listCollections().map((c) => c.name)).toContain('Backlog');
          expect(restoredTarget.artworkId).not.toBeNull();
          expect(fresh.artwork.get(restoredTarget.artworkId!)!.provenance).toBe(
            'hand-drawn test cover',
          );
          console.log(
            `[acceptance] import=3 edit=ok missing-detected=1 bundle=${parsed.formatVersion} ` +
              `restored=3 artwork-provenance=ok`,
          );
        } finally {
          fresh.dispose();
        }
      } finally {
        ctx.dispose();
      }
    } finally {
      rmSync(fixtureRoot, { recursive: true, force: true });
    }
  });
});
