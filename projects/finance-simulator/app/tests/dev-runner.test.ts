import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

// Regression (static wiring test): electron/main.ts only loads a development
// renderer when FS_DEV_SERVER is set, but scripts/dev.mjs previously launched
// Electron with only FS_DEV=1 and never started Vite — a fresh checkout showed
// the backend placeholder (or a stale production bundle). dev.mjs is a
// long-running launcher, so the wiring is asserted on its source instead of
// executing it; the live run is verified manually (see IMPLEMENTATION notes).
const appDir = path.join(path.dirname(fileURLToPath(import.meta.url)), '..');
const devSrc = fs.readFileSync(path.join(appDir, 'scripts', 'dev.mjs'), 'utf8');
const mainSrc = fs.readFileSync(path.join(appDir, 'electron', 'main.ts'), 'utf8');
const viteSrc = fs.readFileSync(path.join(appDir, 'vite.config.ts'), 'utf8');

describe('dev runner wiring', () => {
  it('main process selects the dev renderer via FS_DEV_SERVER (anchor)', () => {
    expect(mainSrc).toContain('FS_DEV_SERVER');
  });
  it('dev.mjs starts the Vite renderer dev server', () => {
    expect(devSrc).toMatch(/vite/);
  });
  it('dev.mjs passes FS_DEV_SERVER to the Electron process', () => {
    expect(devSrc).toContain('FS_DEV_SERVER');
  });
  it('the dev-server URL uses the port configured in vite.config.ts', () => {
    const port = /port:\s*(\d+)/.exec(viteSrc)?.[1];
    expect(port).toBeTruthy();
    expect(devSrc).toContain(port as string);
  });
  // Regression (Codex PR #8, cycle 2): spawning `npx` / `electron.cmd`
  // without a shell cannot work on Windows (.cmd shims are not directly
  // executable), and a spawn with no 'error' listener terminates the
  // runner when a child fails to start.
  it('does not spawn npx or a .cmd shim (Windows-incompatible without a shell)', () => {
    expect(devSrc).not.toMatch(/run\('npx'/);
    expect(devSrc).not.toMatch(/spawn\('npx'/);
    expect(devSrc).not.toContain('electron.cmd');
    expect(devSrc).not.toMatch(/['"]npx['"]/);
  });
  it('launches tools through their Node JS entry points (dev-commands.mjs)', () => {
    expect(devSrc).toContain('dev-commands.mjs');
    expect(devSrc).toMatch(/tscWatchCommand/);
    expect(devSrc).toMatch(/viteCommand/);
    expect(devSrc).toMatch(/electronCommand/);
  });
  it('handles child spawn errors instead of letting them terminate the runner', () => {
    expect(devSrc).toMatch(/\.on\('error',/);
  });
});
