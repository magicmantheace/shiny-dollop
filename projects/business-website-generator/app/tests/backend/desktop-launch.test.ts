/**
 * Desktop launch contract tests (PR #14, Codex round-1 findings): the
 * packaged app must actually start and load its UI —
 *  1. package.json declares the compiled Electron entry point (without a
 *     `main` field, launching the app directory falls back to a
 *     nonexistent index.js);
 *  2. main.ts resolves the renderer from the directory Vite writes to
 *     (dist/renderer), not dist/electron/renderer;
 *  3. the preload runs sandboxed, so it may not require local modules —
 *     its only runtime import is `electron`, and its inlined channel
 *     literals stay in sync with the canonical map in ipc.ts.
 */
import { promises as fs } from 'node:fs';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it, vi } from 'vitest';

vi.mock('electron', () => ({
  ipcMain: { handle: vi.fn() },
}));

import { CHANNELS } from '../../electron/main/ipc.js';

const APP_DIR = fileURLToPath(new URL('../..', import.meta.url));

async function readAppFile(rel: string): Promise<string> {
  return fs.readFile(path.join(APP_DIR, rel), 'utf8');
}

describe('desktop launch contract', () => {
  it('package.json declares the compiled Electron entry point', async () => {
    const pkg = JSON.parse(await readAppFile('package.json')) as { main?: string };
    expect(pkg.main).toBe('dist/electron/main/main.js');
    // The declared entry is what tsconfig.main.json compiles this source to.
    await expect(fs.stat(path.join(APP_DIR, 'electron/main/main.ts'))).resolves.toBeDefined();
  });

  it('main.ts resolves the renderer from the Vite output directory', async () => {
    const main = await readAppFile('electron/main/main.ts');
    // Compiled main sits in dist/electron/main; Vite writes dist/renderer.
    expect(main).toContain("path.join(__dirname, '..', '..', 'renderer', 'index.html')");
    expect(main).not.toContain("path.join(__dirname, '..', 'renderer', 'index.html')");
    const viteConfig = await readAppFile('vite.config.ts');
    expect(viteConfig).toContain("outDir: 'dist/renderer'");
    expect(path.join('dist/electron/main', '..', '..', 'renderer', 'index.html')).toBe(
      path.join('dist/renderer', 'index.html'),
    );
    // The preload path stays one level up: it compiles to dist/electron/preload.js.
    expect(main).toContain("path.join(__dirname, '..', 'preload.js')");
    expect(path.join('dist/electron/main', '..', 'preload.js')).toBe(
      path.join('dist/electron', 'preload.js'),
    );
  });

  it('the preload has no runtime imports beyond electron (sandboxed)', async () => {
    const preload = await readAppFile('electron/preload.ts');
    const runtimeImports = [...preload.matchAll(/^import\s+(?!type\b)[^;]*?from\s+'([^']+)'/gm)].map(
      (m) => m[1],
    );
    expect(runtimeImports).toEqual(['electron']);
    expect(preload).not.toMatch(/\brequire\s*\(/);
  });

  it('the inlined preload channel literals stay in sync with ipc CHANNELS', async () => {
    const preload = await readAppFile('electron/preload.ts');
    const literals = [...preload.matchAll(/'(bwg:[a-z]+:[a-zA-Z]+)'/g)].map((m) => m[1]).sort();
    expect(literals).toEqual(Object.values(CHANNELS).sort());
  });
});
