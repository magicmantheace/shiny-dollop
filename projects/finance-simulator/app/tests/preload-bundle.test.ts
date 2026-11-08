import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { beforeAll, describe, expect, it } from 'vitest';

// Regression (Codex PR #8, round 1): electron/main.ts runs the preload
// with `sandbox: true`, and a sandboxed preload cannot require relative
// modules. The old plain-tsc build emitted
// `require("../shared/ipc-channels")` into dist/electron/preload.js, so
// the preload died before exposing `window.sim` and every renderer call
// (debts/income CRUD, simulation, export) was dead in the production app.
// The preload is now bundled into one script (vite.preload.config.ts)
// with only `electron` external. These tests build the real artifact via
// the package script and then execute it in a sandbox simulation where
// the ONLY resolvable module is a stub `electron` — exactly the
// environment a sandboxed preload runs in.
const appDir = path.join(path.dirname(fileURLToPath(import.meta.url)), '..');
const bundlePath = path.join(appDir, 'dist', 'electron', 'preload.js');
let bundleSrc = '';

beforeAll(() => {
  execFileSync('npm', ['run', 'build:preload'], { cwd: appDir, stdio: 'pipe' });
  bundleSrc = fs.readFileSync(bundlePath, 'utf8');
}, 120_000);

describe('built preload bundle (sandbox contract)', () => {
  it('contains no relative require — a sandboxed preload cannot resolve one', () => {
    expect(bundleSrc).not.toMatch(/require\(\s*["']\./);
  });

  it('keeps electron external and inlines the local channel constants', () => {
    expect(bundleSrc).toMatch(/require\(\s*["']electron["']\)/);
    expect(bundleSrc).toContain('sim:debts/list');
    expect(bundleSrc).toContain('exposeInMainWorld');
  });

  it('executes with only `electron` available and exposes a working window.sim', () => {
    const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'fs-preload-sandbox-'));
    try {
      const electronDir = path.join(tmp, 'node_modules', 'electron');
      fs.mkdirSync(electronDir, { recursive: true });
      fs.writeFileSync(
        path.join(electronDir, 'package.json'),
        JSON.stringify({ name: 'electron', version: '0.0.0', main: 'index.js' }),
      );
      // Stub of the only module a sandboxed preload may require. Records
      // the exposed API and every IPC call; answers with the IpcResult
      // envelope the main process sends ({ ok, data } / { ok, error }).
      fs.writeFileSync(
        path.join(electronDir, 'index.js'),
        [
          'const calls = [];',
          'globalThis.__simBridge = { calls, exposed: null };',
          'module.exports = {',
          '  contextBridge: {',
          '    exposeInMainWorld(key, api) { globalThis.__simBridge.exposed = { key, api }; },',
          '  },',
          '  ipcRenderer: {',
          '    invoke(channel, payload) {',
          '      calls.push({ channel, payload });',
          "      if (channel === 'sim:simulate/run') {",
          "        return Promise.resolve({ ok: false, error: { message: 'boom' } });",
          '      }',
          "      return Promise.resolve({ ok: true, data: ['sentinel'] });",
          '    },',
          '  },',
          '};',
          '',
        ].join('\n'),
      );
      fs.copyFileSync(bundlePath, path.join(tmp, 'preload.js'));
      fs.writeFileSync(
        path.join(tmp, 'harness.cjs'),
        [
          "require('./preload.js');",
          '(async () => {',
          '  const bridge = globalThis.__simBridge;',
          "  if (!bridge || !bridge.exposed) throw new Error('preload exposed nothing');",
          "  if (bridge.exposed.key !== 'sim') throw new Error('wrong exposure key');",
          '  const data = await bridge.exposed.api.debts.list();',
          "  if (JSON.stringify(data) !== '[\"sentinel\"]') throw new Error('bad invoke result');",
          "  if (!bridge.calls.some((c) => c.channel === 'sim:debts/list')) {",
          "    throw new Error('debts.list did not use the inlined channel');",
          '  }',
          '  let rejected = null;',
          '  try { await bridge.exposed.api.simulate.run(100); } catch (e) { rejected = e; }',
          "  if (!rejected || rejected.message !== 'boom') throw new Error('error envelope not surfaced');",
          "  console.log('PRELOAD_BUNDLE_OK');",
          '})().catch((e) => { console.error(e); process.exit(1); });',
          '',
        ].join('\n'),
      );
      const out = execFileSync(process.execPath, [path.join(tmp, 'harness.cjs')], {
        cwd: tmp,
        encoding: 'utf8',
      });
      expect(out).toContain('PRELOAD_BUNDLE_OK');
    } finally {
      fs.rmSync(tmp, { recursive: true, force: true });
    }
  }, 30_000);
});
