#!/usr/bin/env node
/**
 * Development runner: builds main + preload once, starts the vite dev
 * server for the renderer, and launches Electron against it.
 */
import { spawn, spawnSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const appDir = path.join(path.dirname(fileURLToPath(import.meta.url)), '..');
const electronBin = path.join(
  appDir,
  'node_modules',
  '.bin',
  process.platform === 'win32' ? 'electron.cmd' : 'electron',
);

for (const args of [['run', 'build:main'], ['run', 'build:preload']]) {
  const r = spawnSync('npm', args, { stdio: 'inherit', cwd: appDir });
  if (r.status !== 0) process.exit(r.status ?? 1);
}

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

run('npx', ['vite', '--port', '5180', '--strictPort']);
setTimeout(() => {
  run(electronBin, ['--no-sandbox', path.join(appDir, 'dist', 'main', 'main.js')], {
    env: { ...process.env, DRABBIT_DEV_SERVER: 'http://localhost:5180' },
  });
}, 1500);
