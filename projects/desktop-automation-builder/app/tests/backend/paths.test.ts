// Built-app layout + sandboxed-preload self-containment.
//
// Regression coverage for two launch blockers:
//  - the main process loaded the renderer from `dist/electron/renderer`
//    while Vite writes it to `dist/renderer` (blank window);
//  - the preload imported a local channels module, which a sandboxed
//    preload's restricted `require` cannot load (window.dab never set).
import { existsSync, readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { describe, expect, it } from 'vitest';
import { preloadScriptPath, rendererIndexPath } from '../../electron/main/paths.js';
import { DAB_IPC_CHANNELS } from '../../shared/types.js';

/** Locate the app root (the folder holding electron/) from the test cwd. */
function appFile(rel: string): string {
  let dir = process.cwd();
  for (let i = 0; i < 8; i++) {
    const candidate = join(dir, rel);
    if (existsSync(candidate)) return candidate;
    const parent = dirname(dir);
    if (parent === dir) break;
    dir = parent;
  }
  throw new Error(`app file not found from cwd: ${rel}`);
}

function readAppFile(rel: string): string {
  return readFileSync(appFile(rel), 'utf8');
}

const MAIN_DIR = join('/app', 'dist', 'electron', 'main');

describe('built-app paths', () => {
  it('resolves the renderer from dist/renderer, two levels above main', () => {
    expect(rendererIndexPath(MAIN_DIR)).toBe(join('/app', 'dist', 'renderer', 'index.html'));
  });

  it('resolves the preload from dist/electron/preload, one level above main', () => {
    expect(preloadScriptPath(MAIN_DIR)).toBe(
      join('/app', 'dist', 'electron', 'preload', 'preload.js'),
    );
  });

  it('main.ts loads both through the path helpers', () => {
    const src = readAppFile('electron/main/main.ts');
    expect(src).toContain('rendererIndexPath(__dirname)');
    expect(src).toContain('preloadScriptPath(__dirname)');
  });
});

describe('sandboxed preload self-containment', () => {
  const src = readAppFile('electron/preload/preload.ts');

  it('has no runtime import of a local module (sandboxed require cannot load one)', () => {
    expect(src).not.toMatch(/from\s+['"]\.\/channels/);
    expect(src).not.toContain('require(');
    // The only runtime import allowed is Electron itself; shared/types is
    // imported type-only and erased at compile time.
    const runtimeImports = [...src.matchAll(/^import\s+(?!type\b)[^;]*?from\s+['"]([^'"]+)['"]/gm)].map(
      (m) => m[1],
    );
    expect(runtimeImports).toEqual(['electron']);
  });

  it('inlines exactly the DAB_IPC_CHANNELS values', () => {
    for (const channel of DAB_IPC_CHANNELS) {
      expect(src).toContain(`'${channel}'`);
    }
  });
});
