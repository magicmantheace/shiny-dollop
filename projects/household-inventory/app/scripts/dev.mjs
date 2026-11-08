#!/usr/bin/env node
/**
 * Development runner: builds main+preload with tsc (watch) and launches
 * Electron. The renderer dev server (vite) is Worker B's scope; until it is
 * wired, the main window shows the backend placeholder page.
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

// 2. Electron, once the first build lands.
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
    env: { ...process.env, HI_DEV: '1' },
  });
}

setTimeout(startElectron, 8000);
