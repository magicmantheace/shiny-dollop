import { describe, expect, it } from 'vitest';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const appDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');

/**
 * Regression test: the preload runs sandboxed (sandbox: true), and a
 * sandboxed preload cannot require() local files — only a small allowlist
 * of built-ins. When build:preload was a plain tsc emit, the compiled
 * preload contained require('../../shared/ipc-channels') and threw before
 * contextBridge.exposeInMainWorld('concreteOps', …) could run, leaving the
 * renderer with no API at all. The preload must therefore be built as one
 * bundled script whose only require is 'electron'.
 */
describe('preload bundle (sandboxed)', () => {
  it(
    'builds a single self-contained script that only requires electron',
    { timeout: 180_000 },
    () => {
      execFileSync('npm', ['run', 'build:preload', '--silent'], {
        cwd: appDir,
        stdio: 'pipe',
        timeout: 170_000,
      });
      const out = fs.readFileSync(path.join(appDir, 'dist', 'electron', 'preload', 'index.js'), 'utf8');

      const requires = [...out.matchAll(/require\(\s*["']([^"']+)["']\s*\)/g)].map((m) => m[1]);
      expect(requires.length).toBeGreaterThan(0);
      expect(new Set(requires)).toEqual(new Set(['electron']));

      // The shared IPC channel constants are inlined into the bundle…
      expect(out).toContain('concrete.customers.list');
      expect(out).toContain('concrete.invoices.create');
      // …and the API is still exposed under the expected name.
      expect(out).toContain('concreteOps');
      expect(out).toContain('exposeInMainWorld');
    },
  );

  it('keeps the sandbox enabled in the main process', () => {
    const main = fs.readFileSync(path.join(appDir, 'electron', 'main', 'index.ts'), 'utf8');
    expect(main).toContain('sandbox: true');
    expect(main).toContain('contextIsolation: true');
  });
});
