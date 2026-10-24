#!/usr/bin/env node
// Smoke test: launch the built app headlessly under xvfb (Linux) and check
// the window opens and reports ready, then quit.
import { spawn } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const appDir = path.join(__dirname, '..');
const main = path.join(appDir, 'dist', 'electron', 'main', 'index.js');

const child = spawn('npx', ['electron', '--no-sandbox', main, '--smoke'], {
  cwd: appDir,
  shell: true,
  env: { ...process.env, VCC_SMOKE: '1' },
});

let out = '';
child.stdout.on('data', (d) => {
  out += d.toString();
});
child.stderr.on('data', (d) => {
  out += d.toString();
});

const timeout = setTimeout(() => {
  console.error('SMOKE TIMEOUT — output so far:\n' + out.slice(-2000));
  child.kill('SIGKILL');
  process.exit(1);
}, 45000);

child.on('exit', (code) => {
  clearTimeout(timeout);
  // Electron exits 0 on clean quit; anything else fails the smoke test.
  if (code === 0) {
    console.log('SMOKE PASS');
    process.exit(0);
  }
  console.error('SMOKE FAIL (exit ' + code + ')\n' + out.slice(-2000));
  process.exit(1);
});

