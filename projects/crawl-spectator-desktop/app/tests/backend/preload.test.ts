import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import { SPECTATOR_IPC_CHANNELS } from '../../shared/types';

const appRoot = join(__dirname, '..', '..');
const preloadSource = readFileSync(join(appRoot, 'electron', 'preload', 'preload.ts'), 'utf8');

describe('sandboxed preload hygiene', () => {
  it('uses only type-only imports from shared code (nothing runtime to require)', () => {
    const runtimeSharedImports = preloadSource
      .split('\n')
      .filter((line) => /^\s*import\s/.test(line) && line.includes('shared/') && !/^\s*import\s+type\b/.test(line));
    expect(runtimeSharedImports).toEqual([]);
  });

  it('channel literals in the preload exactly match SPECTATOR_IPC_CHANNELS', () => {
    const literals = new Set([...preloadSource.matchAll(/'(spectator:[a-z-]+)'/g)].map((m) => m[1]));
    expect(literals).toEqual(new Set(Object.values(SPECTATOR_IPC_CHANNELS)));
  });

  it('compiled preload (when built) requires nothing but electron', () => {
    const compiled = join(appRoot, 'dist', 'electron', 'preload', 'preload.js');
    if (!existsSync(compiled)) return; // build artifact check runs in the smoke flow
    const js = readFileSync(compiled, 'utf8');
    const requires = [...js.matchAll(/require\(["']([^"']+)["']\)/g)].map((m) => m[1]);
    expect(new Set(requires)).toEqual(new Set(['electron']));
  });
});
