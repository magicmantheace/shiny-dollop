import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

function readPreloadSource(): string {
  const candidates = [
    join(process.cwd(), 'electron/preload/preload.ts'),
    join(process.cwd(), 'projects/ai-dungeon-master/app/electron/preload/preload.ts'),
  ];
  for (const candidate of candidates) {
    if (existsSync(candidate)) return readFileSync(candidate, 'utf8');
  }
  throw new Error(`preload.ts not found; tried: ${candidates.join(', ')}`);
}

const CHANNELS = [
  'aidm:campaigns-list',
  'aidm:campaigns-create',
  'aidm:campaigns-get',
  'aidm:campaigns-delete',
  'aidm:sessions-list',
  'aidm:sessions-create',
  'aidm:sessions-update-notes',
  'aidm:sessions-end',
  'aidm:characters-list',
  'aidm:characters-create',
  'aidm:characters-update',
  'aidm:characters-delete',
  'aidm:dice-roll',
  'aidm:check-roll',
  'aidm:log-list',
  'aidm:log-add-note',
  'aidm:encounters-start',
  'aidm:encounters-get-active',
  'aidm:encounters-advance-turn',
  'aidm:encounters-apply-damage',
  'aidm:encounters-apply-heal',
  'aidm:encounters-end',
  'aidm:memory-list',
  'aidm:memory-create',
  'aidm:memory-update',
  'aidm:memory-delete',
  'aidm:memory-search',
  'aidm:narrate',
  'aidm:settings-get',
  'aidm:settings-update',
  'aidm:export-campaign',
  'aidm:import-campaign',
  'aidm:import-worldbuilding',
  'aidm:import-dungeon-manifest',
];

describe('preload hygiene', () => {
  const source = readPreloadSource();

  it('has no runtime import from shared (every shared import is import type)', () => {
    const importLines = source.split('\n').filter((line) => /^\s*import\b/.test(line));
    const sharedImports = importLines.filter((line) => line.includes('shared'));
    expect(sharedImports.length).toBeGreaterThan(0);
    for (const line of sharedImports) {
      expect(line).toMatch(/^\s*import\s+type\b/);
    }
  });

  it('contains no require calls', () => {
    expect(source).not.toContain('require(');
  });

  it('uses literal aidm channel strings and exposes window.aidm', () => {
    for (const channel of CHANNELS) {
      expect(source).toContain(`'${channel}'`);
    }
    expect(source).toContain("exposeInMainWorld('aidm'");
  });

  it('built preload (when present) has no runtime require of project modules', () => {
    const built = join(process.cwd(), 'dist/electron/preload/preload.js');
    if (!existsSync(built)) return; // build not run; source checks above cover it
    const js = readFileSync(built, 'utf8');
    expect(js).not.toMatch(/require\(["']\.\./);
    expect(js).not.toMatch(/require\(["'].*shared/);
  });
});
