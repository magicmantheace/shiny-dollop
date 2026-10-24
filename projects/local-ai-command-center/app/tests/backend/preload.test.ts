import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { LACC_IPC_CHANNELS } from '../../shared/types.js';

// Tests run with the app directory as cwd (npm test in app/).
function read(rel: string): string {
  return readFileSync(join(process.cwd(), rel), 'utf8');
}

describe('sandboxed preload', () => {
  const src = read('electron/preload/preload.ts');

  it('has no runtime import of a local module (sandboxed preloads cannot require them)', () => {
    expect(src).not.toContain("from './channels.js'");
    // Every import except `electron` must be a type-only import (erased at compile time).
    const imports = src.split('\n').filter((l) => l.startsWith('import '));
    for (const line of imports) {
      if (line.includes("from 'electron'")) continue;
      expect(line, `runtime local import in preload: ${line}`).toMatch(/^import type /);
    }
  });

  it('inlines a channel map identical to LACC_IPC_CHANNELS', () => {
    const inlined = [...src.matchAll(/(\w+): '(lacc:[^']+)'/g)].map((m) => [m[1], m[2]]);
    expect(Object.fromEntries(inlined)).toEqual(LACC_IPC_CHANNELS);
    expect(src).toContain("exposeInMainWorld('lacc'");
  });

  it('unwraps the IPC success/error envelope instead of relying on thrown errors', () => {
    // ipcMain.handle loses structured error codes across the boundary, so the
    // main side returns { ok, value | error } as data and the preload unwraps.
    expect(src).toContain('ok: false');
    expect(src).toContain('throw env.error');
    expect(src).toContain('ipcRenderer.invoke');
  });

  it('main window does not disable the sandbox', () => {
    const main = read('electron/main/main.ts');
    expect(main).not.toContain('sandbox: false');
    expect(main).toContain('contextIsolation: true');
    expect(main).toContain('nodeIntegration: false');
  });
});
