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
});
