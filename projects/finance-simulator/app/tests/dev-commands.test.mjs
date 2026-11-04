import path from 'node:path';
import { describe, expect, it } from 'vitest';
import { electronCommand, tscWatchCommand, viteCommand, vitePreloadWatchCommand } from '../scripts/dev-commands.mjs';

// Regression (Codex PR #8, cycle 2): scripts/dev.mjs spawned `npx` and the
// `electron.cmd` shim with no shell. On Windows those are .cmd shims, which
// Node cannot execute directly, so `npm run dev` failed there. Every tool
// must instead be launched as `node <js-entry-point>` — the same files the
// shims forward to — which works identically on POSIX and Windows.
const appDir = path.join('synthetic', 'app');
const execPath = path.join('synthetic', 'node');

describe('dev launch commands (no Windows command shims)', () => {
  it('launches tsc through its JS entry point with Node, not npx', () => {
    const spec = tscWatchCommand(appDir, 'tsconfig.main.json', execPath);
    expect(spec.command).toBe(execPath);
    expect(spec.command).not.toMatch(/npx|cmd$/);
    expect(spec.args[0]).toBe(path.join(appDir, 'node_modules', 'typescript', 'bin', 'tsc'));
    expect(spec.args.slice(1)).toEqual(['-p', 'tsconfig.main.json', '--watch', '--preserveWatchOutput']);
  });

  it('launches Vite through its JS entry point with Node, not npx', () => {
    const spec = viteCommand(appDir, 5177, execPath);
    expect(spec.command).toBe(execPath);
    expect(spec.args[0]).toBe(path.join(appDir, 'node_modules', 'vite', 'bin', 'vite.js'));
    expect(spec.args.slice(1)).toEqual(['--port', '5177', '--strictPort']);
  });

  it('rebuilds the preload as a Vite bundle in watch mode, not tsc output', () => {
    // The sandboxed preload must stay a single self-contained script in
    // dev too (see vite.preload.config.ts); tsc watch output would
    // restore the relative require the sandbox cannot load.
    const spec = vitePreloadWatchCommand(appDir, execPath);
    expect(spec.command).toBe(execPath);
    expect(spec.args[0]).toBe(path.join(appDir, 'node_modules', 'vite', 'bin', 'vite.js'));
    expect(spec.args.slice(1)).toEqual(['build', '--config', 'vite.preload.config.ts', '--watch']);
  });

  it('launches Electron through cli.js with Node, not the electron.cmd shim', () => {
    const entry = path.join(appDir, 'dist', 'electron', 'main.js');
    const spec = electronCommand(appDir, entry, ['--no-sandbox'], execPath);
    expect(spec.command).toBe(execPath);
    expect(spec.args[0]).toBe(path.join(appDir, 'node_modules', 'electron', 'cli.js'));
    expect(spec.args[0]).not.toMatch(/\.cmd$/);
    expect(spec.args.slice(1)).toEqual(['--no-sandbox', entry]);
  });

  it('never produces a .cmd, npx, or shell-dependent command', () => {
    const specs = [
      tscWatchCommand(appDir, 'tsconfig.preload.json', execPath),
      viteCommand(appDir, 5177, execPath),
      electronCommand(appDir, 'main.js', [], execPath),
    ];
    for (const spec of specs) {
      expect(spec.command).not.toMatch(/\.cmd$|^npx/);
      expect(spec.args.join(' ')).not.toMatch(/\.cmd\b/);
    }
  });
});
