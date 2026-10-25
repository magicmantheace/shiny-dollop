import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { CampaignService } from '../../electron/main/service.js';
import { openDatabase } from '../../electron/main/store.js';

export function makeFixture() {
  const dir = mkdtempSync(join(tmpdir(), 'aidm-test-'));
  const dbPath = join(dir, 'test.sqlite');
  const db = openDatabase(dbPath);
  const service = new CampaignService(db);
  return { dir, dbPath, db, service };
}

/** Reopen the same database file with a fresh service (simulates an app restart). */
export function reopen(fx: ReturnType<typeof makeFixture>): CampaignService {
  fx.db.close();
  const db = openDatabase(fx.dbPath);
  fx.db = db;
  return new CampaignService(db);
}

/** A minimal worldbuilding-manager.project v1 backup, in the real export shape. */
export const WORLDBUILDING_FIXTURE = JSON.stringify(
  {
    format: 'worldbuilding-manager.project',
    formatVersion: '1.0.0',
    entities: [
      {
        id: 'wb-char-1',
        type: 'character',
        name: 'Sella the Ferryman',
        role: 'guide',
        description: 'Rows travelers across the Mire.',
        body: 'Owes a debt to the Lantern Court.',
        storyDate: null,
        orderKey: null,
        bornOrder: null,
        diedOrder: null,
        tags: ['mire', 'npc'],
        createdAt: '2026-10-23T00:00:00.000Z',
        updatedAt: '2026-10-23T00:00:00.000Z',
      },
      {
        id: 'wb-loc-1',
        type: 'location',
        name: 'The Drowned Tollhouse',
        role: '',
        description: 'A tollhouse sunk to its eaves.',
        body: '',
        storyDate: null,
        orderKey: null,
        bornOrder: null,
        diedOrder: null,
        tags: ['mire'],
        createdAt: '2026-10-23T00:00:00.000Z',
        updatedAt: '2026-10-23T00:00:00.000Z',
      },
      {
        id: 'wb-fac-1',
        type: 'faction',
        name: 'The Lantern Court',
        role: '',
        description: 'Collectors of unpaid debts.',
        body: '',
        storyDate: null,
        orderKey: null,
        bornOrder: null,
        diedOrder: null,
        tags: [],
        createdAt: '2026-10-23T00:00:00.000Z',
        updatedAt: '2026-10-23T00:00:00.000Z',
      },
    ],
    links: [],
    revisions: [],
  },
  null,
  2,
);

/** A minimal procedural-dungeon-designer/map v1 manifest, in the real export shape. */
export const DUNGEON_FIXTURE = JSON.stringify(
  {
    format: 'procedural-dungeon-designer/map',
    formatVersion: '1.0.0',
    name: 'Sunken Crypt of Bells',
    map: {
      params: {
        seed: 'crypt-seed',
        gridWidth: 24,
        gridHeight: 18,
        roomCount: 3,
        theme: 'sunken-crypt',
        difficulty: 2,
      },
      gridWidth: 24,
      gridHeight: 18,
      tiles: [],
      rooms: [
        {
          id: 'room-1',
          name: 'Bell Antechamber',
          x: 1, y: 1, w: 5, h: 4, cx: 3, cy: 3,
          isEntrance: true,
          placements: [],
        },
        {
          id: 'room-2',
          name: 'Flooded Vault',
          x: 8, y: 1, w: 5, h: 4, cx: 10, cy: 3,
          isEntrance: false,
          placements: [
            { id: 'p1', kind: 'encounter', key: 'pale-warden', name: 'Pale Warden', cost: 3 },
            { id: 'p2', kind: 'treasure', key: 'bell-hoard', name: 'Bell Hoard', cost: 1 },
          ],
        },
      ],
      budgetLimit: 10,
      budgetUsed: 4,
    },
  },
  null,
  2,
);
