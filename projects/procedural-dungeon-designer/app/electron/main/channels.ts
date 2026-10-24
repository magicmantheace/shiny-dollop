// IPC channel names for the Procedural Dungeon Designer.
// The channel strings are the wire contract between preload and main;
// the sandboxed preload repeats them as literals (it cannot import this
// module at runtime), and a backend test keeps the two in step via the
// method-name mapping below.
import type { PddApi } from '../../shared/types.js';

export const PDD_CHANNELS = {
  themesList: 'pdd:themes-list',
  generate: 'pdd:generate',
  validateMap: 'pdd:validate-map',
  dungeonsSave: 'pdd:dungeons-save',
  dungeonsList: 'pdd:dungeons-list',
  dungeonsGet: 'pdd:dungeons-get',
  dungeonsDelete: 'pdd:dungeons-delete',
  placementsAdd: 'pdd:placements-add',
  placementsRemove: 'pdd:placements-remove',
  placementsMove: 'pdd:placements-move',
  exportJson: 'pdd:export-json',
  exportMarkdown: 'pdd:export-markdown',
  importJson: 'pdd:import-json',
} as const satisfies Record<keyof PddApi, string>;

export type PddMethodName = keyof typeof PDD_CHANNELS;
