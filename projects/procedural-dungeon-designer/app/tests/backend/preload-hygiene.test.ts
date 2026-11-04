import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

function readPreloadSource(): string {
  const candidates = [
    join(process.cwd(), 'electron/preload/preload.ts'),
    join(process.cwd(), 'projects/procedural-dungeon-designer/app/electron/preload/preload.ts'),
  ];
  for (const candidate of candidates) {
    if (existsSync(candidate)) return readFileSync(candidate, 'utf8');
  }
  throw new Error(`preload.ts not found; tried: ${candidates.join(', ')}`);
}

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

  it('uses literal pdd channel strings and exposes window.pdd', () => {
    for (const channel of [
      'pdd:themes-list',
      'pdd:generate',
      'pdd:validate-map',
      'pdd:dungeons-save',
      'pdd:dungeons-list',
      'pdd:dungeons-get',
      'pdd:dungeons-delete',
      'pdd:placements-add',
      'pdd:placements-remove',
      'pdd:placements-move',
      'pdd:export-json',
      'pdd:export-markdown',
      'pdd:import-json',
    ]) {
      expect(source).toContain(`'${channel}'`);
    }
    expect(source).toContain("exposeInMainWorld('pdd'");
  });
});
