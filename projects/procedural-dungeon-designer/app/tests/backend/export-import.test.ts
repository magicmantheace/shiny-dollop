import { describe, expect, it } from 'vitest';
import {
  EXPORT_FORMAT,
  EXPORT_FORMAT_VERSION,
  buildExport,
  stableStringify,
} from '../../shared/export.js';
import type { SavedDungeon } from '../../shared/types.js';
import { BASE_PARAMS, breakableFixture, cloneMap, makeFixture } from './helpers.js';

async function savedFixture(name = 'Export Host'): Promise<{
  service: ReturnType<typeof makeFixture>['service'];
  db: ReturnType<typeof makeFixture>['db'];
  saved: SavedDungeon;
}> {
  const { service, db } = makeFixture();
  const map = await service.generate(BASE_PARAMS);
  const saved = await service.dungeonsSave({ name, map });
  return { service, db, saved };
}

describe('export / import', () => {
  it('buildExport is deterministic: two calls are byte-identical', async () => {
    const { db, saved } = await savedFixture();
    expect(buildExport(saved)).toBe(buildExport(saved));
    db.close();
  });

  it('service export -> import round-trip reproduces the map exactly', async () => {
    const { service, db, saved } = await savedFixture();
    const text = await service.exportJson(saved.id);
    const imported = await service.importJson(text);
    expect(imported.id).not.toBe(saved.id);
    expect(imported.name).toBe(saved.name);
    expect(imported.map).toEqual(saved.map);
    expect(stableStringify(imported.map)).toBe(stableStringify(saved.map));
    db.close();
  });

  it('corrupt JSON rejects with IMPORT_INVALID', async () => {
    const { service, db } = await savedFixture();
    await expect(service.importJson('{not json')).rejects.toMatchObject({
      code: 'IMPORT_INVALID',
    });
    db.close();
  });

  it('a wrong envelope format rejects with IMPORT_INVALID', async () => {
    const { service, db } = await savedFixture();
    const wrong = JSON.stringify({ format: 'someone-elses/format', formatVersion: '1.0.0', name: 'X', map: {} });
    await expect(service.importJson(wrong)).rejects.toMatchObject({ code: 'IMPORT_INVALID' });
    db.close();
  });

  it("formatVersion '2.0.0' rejects with IMPORT_VERSION_UNSUPPORTED", async () => {
    const { service, db, saved } = await savedFixture();
    const envelope = JSON.parse(buildExport(saved)) as Record<string, unknown>;
    envelope.formatVersion = '2.0.0';
    await expect(service.importJson(JSON.stringify(envelope))).rejects.toMatchObject({
      code: 'IMPORT_VERSION_UNSUPPORTED',
    });
    db.close();
  });

  it('oversized text rejects with INPUT_TOO_LARGE', async () => {
    const { service, db } = await savedFixture();
    await expect(service.importJson('x'.repeat(1_000_001))).rejects.toMatchObject({
      code: 'INPUT_TOO_LARGE',
    });
    db.close();
  });

  it('importing a disconnected map rejects with IMPORT_INVALID', async () => {
    const { service, db } = makeFixture();
    const { broken } = breakableFixture();
    const text = stableStringify({
      format: EXPORT_FORMAT,
      formatVersion: EXPORT_FORMAT_VERSION,
      name: 'Broken Import',
      map: broken,
    });
    await expect(service.importJson(text)).rejects.toMatchObject({ code: 'IMPORT_INVALID' });
    db.close();
  });

  it('exportMarkdown mentions the dungeon, seed and budget', async () => {
    const { service, db, saved } = await savedFixture('Markdown Host');
    const md = await service.exportMarkdown(saved.id);
    expect(md).toContain('# Markdown Host');
    expect(md).toContain(BASE_PARAMS.seed);
    expect(md).toContain(`${saved.map.budgetUsed} / ${saved.map.budgetLimit}`);
    db.close();
  });

  it('import rejects placement costs zeroed to defeat the budget', async () => {
    const { service, db, saved } = await savedFixture();
    const envelope = JSON.parse(buildExport(saved)) as { map: ReturnType<typeof cloneMap> };
    let tamperedCount = 0;
    for (const room of envelope.map.rooms) {
      for (const placement of room.placements) {
        placement.cost = 0;
        tamperedCount++;
      }
    }
    expect(tamperedCount).toBeGreaterThan(0);
    envelope.map.budgetUsed = 0;
    await expect(service.importJson(JSON.stringify(envelope))).rejects.toMatchObject({
      code: 'IMPORT_INVALID',
    });
    db.close();
  });

  it('import rejects a map whose entrance center is a wall', async () => {
    const { service, db, saved } = await savedFixture();
    const envelope = JSON.parse(buildExport(saved)) as { map: ReturnType<typeof cloneMap> };
    const entrance =
      envelope.map.rooms.find((r) => r.isEntrance) ?? envelope.map.rooms[0]!;
    const grid = envelope.map.tiles.map((row) => row.split(''));
    grid[entrance.cy]![entrance.cx] = '#';
    envelope.map.tiles = grid.map((row) => row.join(''));
    await expect(service.importJson(JSON.stringify(envelope))).rejects.toMatchObject({
      code: 'IMPORT_INVALID',
    });
    db.close();
  });

  it('a tampered stored budgetUsed is recomputed on import', async () => {
    const { service, db, saved } = await savedFixture();
    const envelope = JSON.parse(buildExport(saved)) as { map: ReturnType<typeof cloneMap> };
    envelope.map.budgetUsed = 999_999;
    const imported = await service.importJson(JSON.stringify(envelope));
    expect(imported.map.budgetUsed).toBe(saved.map.budgetUsed);
    db.close();
  });
});
