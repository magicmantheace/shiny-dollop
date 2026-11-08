// Original themes for the Procedural Dungeon Designer.
// All names, creatures, traps and hazards here are original, generic
// fantasy content written for this project — no proprietary RPG material.

import type { PlacementKind, ThemeInfo } from './types.js';

export const THEMES: readonly ThemeInfo[] = [
  {
    id: 'sunken-crypt',
    name: 'Sunken Crypt',
    tagline: 'A drowned burial complex of silt, still water and pale guardians.',
    palette: {
      wall: '#141d1a',
      floor: '#3d5a57',
      corridor: '#527a72',
      entrance: '#d9b45b',
      accent: '#7fd1c0',
      text: '#e8f1ee',
    },
    roomNamePrefixes: ['Sunken', 'Mossy', 'Silent', 'Flooded', 'Forgotten', 'Pale', 'Hollow', 'Drowned'],
    roomNameNouns: ['Vault', 'Sepulcher', 'Ossuary', 'Gallery', 'Cistern', 'Shrine', 'Passage', 'Chamber'],
    tables: {
      encounter: [
        { key: 'tide-rat-pack', name: 'Tide Rat Pack', cost: 6 },
        { key: 'pale-warden', name: 'Pale Warden', cost: 10 },
        { key: 'mire-crawler', name: 'Mire Crawler', cost: 8 },
        { key: 'bonepicker-swarm', name: 'Bonepicker Swarm', cost: 5 },
        { key: 'drowned-sentry', name: 'Drowned Sentry', cost: 7 },
      ],
      trap: [
        { key: 'silt-dart-trap', name: 'Silt Dart Trap', cost: 4 },
        { key: 'false-step-pit', name: 'False-Step Pit', cost: 6 },
        { key: 'weeping-rune', name: 'Weeping Rune', cost: 8 },
      ],
      hazard: [
        { key: 'black-mold-colony', name: 'Black Mold Colony', cost: 5 },
        { key: 'unstable-ceiling', name: 'Unstable Ceiling', cost: 7 },
        { key: 'stagnant-floodwater', name: 'Stagnant Floodwater', cost: 4 },
      ],
      treasure: [
        { key: 'barnacled-coffer', name: 'Barnacled Coffer', cost: 3 },
        { key: 'tide-glass-cache', name: 'Tide-Glass Cache', cost: 5 },
        { key: 'sunken-offering-bowl', name: 'Sunken Offering Bowl', cost: 2 },
      ],
    },
  },
  {
    id: 'ember-deep',
    name: 'Ember Deep',
    tagline: 'A scorched forge-delving of ash tunnels, slag vents and banked fires.',
    palette: {
      wall: '#211511',
      floor: '#5a3a2e',
      corridor: '#7a4a34',
      entrance: '#ffb347',
      accent: '#ff7a59',
      text: '#f7ece4',
    },
    roomNamePrefixes: ['Ember', 'Ashen', 'Scorched', 'Cinder', 'Smoldering', 'Obsidian', 'Molten', 'Soot'],
    roomNameNouns: ['Forge', 'Tunnel', 'Vault', 'Chimney', 'Gallery', 'Kiln', 'Passage', 'Chamber'],
    tables: {
      encounter: [
        { key: 'ash-hound-pack', name: 'Ash Hound Pack', cost: 6 },
        { key: 'forge-wraith', name: 'Forge Wraith', cost: 10 },
        { key: 'slag-crawler', name: 'Slag Crawler', cost: 8 },
        { key: 'ember-knight', name: 'Ember Knight', cost: 11 },
        { key: 'soot-bat-swarm', name: 'Soot Bat Swarm', cost: 4 },
      ],
      trap: [
        { key: 'cinder-dart-trap', name: 'Cinder Dart Trap', cost: 4 },
        { key: 'slag-vent-trap', name: 'Slag Vent Trap', cost: 6 },
        { key: 'ember-rune-brand', name: 'Ember Rune Brand', cost: 8 },
      ],
      hazard: [
        { key: 'toxic-fume-pocket', name: 'Toxic Fume Pocket', cost: 6 },
        { key: 'lava-seep', name: 'Lava Seep', cost: 9 },
        { key: 'superheated-floor', name: 'Superheated Floor', cost: 5 },
      ],
      treasure: [
        { key: 'obsidian-cache', name: 'Obsidian Cache', cost: 5 },
        { key: 'forgeheart-gem', name: 'Forgeheart Gem', cost: 8 },
        { key: 'ashwood-coffer', name: 'Ashwood Coffer', cost: 3 },
      ],
    },
  },
];

export function getTheme(id: string): ThemeInfo {
  const theme = THEMES.find((t) => t.id === id);
  if (!theme) throw new Error(`Unknown theme: ${id}`);
  return theme;
}

export function tableEntry(
  theme: ThemeInfo,
  kind: PlacementKind,
  key: string,
): { key: string; name: string; cost: number } | null {
  return theme.tables[kind].find((e) => e.key === key) ?? null;
}

/** Cheapest placement cost across all tables of a theme (generator stop rule). */
export function cheapestCost(theme: ThemeInfo): number {
  let min = Number.POSITIVE_INFINITY;
  for (const kind of Object.keys(theme.tables) as PlacementKind[]) {
    for (const entry of theme.tables[kind]) min = Math.min(min, entry.cost);
  }
  return min;
}
