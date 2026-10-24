#!/usr/bin/env node
/**
 * Development runner: builds main+preload with tsc (watch), starts the
 * renderer dev server (Vite), and launches Electron against it.
 *
 * electron/main.ts only loads a development renderer when FS_DEV_SERVER is
 * set, so Electron is launched with FS_DEV_SERVER pointing at the Vite
 * server below. Without this wiring the window falls back to the backend
 * placeholder (fresh checkout) or a stale production bundle.
 *
 * All children are launched via their JS entry points under Node (see
 * dev-commands.mjs): on Windows the command shims for these tools cannot
 * be spawned without a shell, which previously broke `npm run dev` there.
 */
import { spawn } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { electronCommand, tscWatchCommand, viteCommand } from './dev-commands.mjs';

const root = path.dirname(fileURLToPath(import.meta.url));
const appDir = path.join(root, '..');

// Must match the `server` block in vite.config.ts (port 5177, strictPort).
const DEV_SERVER_PORT = 5177;
const DEV_SERVER_URL = `http://localhost:${DEV_SERVER_PORT}`;

const children = new Set();
function run(cmd, args, opts = {}) {
  const child = spawn(cmd, args, { stdio: 'inherit', cwd: appDir, ...opts });
  children.add(child);
  // Without an 'error' listener a failed spawn (missing binary, EINVAL,
  // ...) is an unhandled EventEmitter error and terminates the runner.
  // Log it and drop the child instead, so the other watchers keep running.
  child.on('error', (err) => {
    console.error(`[dev] failed to start ${cmd}: ${err.message}`);
    children.delete(child);
  });
  child.on('exit', () => children.delete(child));
  return child;
}

function runSpec(spec, opts = {}) {
  return run(spec.command, spec.args, opts);
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
runSpec(tscWatchCommand(appDir, 'tsconfig.main.json'));
runSpec(tscWatchCommand(appDir, 'tsconfig.preload.json'));

// 2. Renderer dev server (Vite). Started before Electron so the URL passed
// via FS_DEV_SERVER is already serving when the window loads.
runSpec(viteCommand(appDir, DEV_SERVER_PORT));

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
  const spec = electronCommand(appDir, entry, ['--no-sandbox']);
  electron = run(spec.command, spec.args, {
    env: { ...process.env, FS_DEV: '1', FS_DEV_SERVER: DEV_SERVER_URL },
  });
}

setTimeout(startElectron, 8000);
