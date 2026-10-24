#!/usr/bin/env node
/**
 * Development runner: builds main+preload with tsc (watch), starts the
 * renderer dev server (Vite), and launches Electron against it.
 *
 * electron/main.ts only loads a development renderer when FS_DEV_SERVER is
 * set, so Electron is launched with FS_DEV_SERVER pointing at the Vite
 * server below. Without this wiring the window falls back to the backend
 * placeholder (fresh checkout) or a stale production bundle.
 */
import { spawn } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.dirname(fileURLToPath(import.meta.url));
const appDir = path.join(root, '..');
const electronBin = path.join(appDir, 'node_modules', '.bin', process.platform === 'win32' ? 'electron.cmd' : 'electron');

// Must match the `server` block in vite.config.ts (port 5177, strictPort).
const DEV_SERVER_PORT = 5177;
const DEV_SERVER_URL = `http://localhost:${DEV_SERVER_PORT}`;

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

// 2. Renderer dev server (Vite). Started before Electron so the URL passed
// via FS_DEV_SERVER is already serving when the window loads.
run('npx', ['vite', '--port', String(DEV_SERVER_PORT), '--strictPort']);

// 3. Electron, once the first build lands.
let electron = null;
function startElectron() {
  if (electron) {
    try {
      electron.kill();
    } catch {
      // ignore
    }
  }
  const entry = path.join(appDir, 'dist', 'electron', 'main.js');
  electron = run(electronBin, ['--no-sandbox', entry], {
    env: { ...process.env, FS_DEV: '1', FS_DEV_SERVER: DEV_SERVER_URL },
  });
}

setTimeout(startElectron, 8000);
