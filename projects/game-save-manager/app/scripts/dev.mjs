#!/usr/bin/env node
/**
 * Development runner: builds main+preload with tsc (watch), serves the
 * renderer with Vite, and launches Electron against the dev server.
 * Restart Electron automatically when main/preload recompile.
 */
import { spawn } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.dirname(fileURLToPath(import.meta.url));
const appDir = path.join(root, '..');
const electronBin = path.join(appDir, 'node_modules', '.bin', process.platform === 'win32' ? 'electron.cmd' : 'electron');

const children = new Set();
function run(cmd, args, opts = {}) {
  const child = spawn(cmd, args, { stdio: 'inherit', cwd: appDir, ...opts });
  children.add(child);
  child.on('exit', () => children.delete(child));
  return child;
}

function shutdown() {
  for (const c of children) {
    try {
      c.kill();
    } catch {
      // ignore
    }
  }
  process.exit(0);
}
process.on('SIGINT', shutdown);
process.on('SIGTERM', shutdown);

// 1. TypeScript watchers for main + preload.
run('npx', ['tsc', '-p', 'tsconfig.main.json', '--watch', '--preserveWatchOutput']);
run('npx', ['tsc', '-p', 'tsconfig.preload.json', '--watch', '--preserveWatchOutput']);

// 2. Vite dev server for the renderer.
const vite = run('npx', ['vite']);

// 3. Electron, started once Vite is up.
let electron = null;
function startElectron() {
  if (electron) {
    try {
      electron.kill();
    } catch {
      // ignore
    }
  }
  console.log('[dev] starting Electron…');
  // Headless Linux (no X server): wrap in xvfb so the window can initialize.
  const needsXvfb = process.platform === 'linux' && !process.env.DISPLAY;
  const cmd = needsXvfb ? 'xvfb-run' : electronBin;
  const args = needsXvfb
    ? ['-a', electronBin, '--no-sandbox', 'dist/electron/main/index.js']
    : ['--no-sandbox', 'dist/electron/main/index.js'];
  electron = run(cmd, args, {
    env: { ...process.env, GSM_DEV_SERVER: 'http://localhost:5174' },
  });
}

vite.on('spawn', () => {
  // Give Vite a moment to come up, then start Electron once.
  setTimeout(startElectron, 2500);
});

console.log('[dev] NOTE: after editing electron/main or electron/preload, restart this command.');
console.log('[dev] Renderer (src/) hot-reloads automatically.');
