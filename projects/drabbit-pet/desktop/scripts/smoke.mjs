#!/usr/bin/env node
/**
 * Headless smoke: builds the app, launches the real Electron binary
 * with DRABBIT_SMOKE=1 against a throwaway userData dir, and passes
 * only when the main process prints SMOKE_OK (both windows loaded the
 * production bundle). Uses xvfb-run when there is no X display.
 *
 * Exit 0 = smoke passed; 1 = build or launch failed; 2 = environment
 * cannot run Electron at all (reported, not faked).
 */
import { spawn, spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const appDir = path.join(path.dirname(fileURLToPath(import.meta.url)), '..');
const electronBin = path.join(
  appDir,
  'node_modules',
  '.bin',
  process.platform === 'win32' ? 'electron.cmd' : 'electron',
);

if (!fs.existsSync(electronBin)) {
  console.error('SMOKE_ENV_MISSING: electron binary not installed (run npm install first)');
  process.exit(2);
}

const build = spawnSync('npm', ['run', 'build'], { stdio: 'inherit', cwd: appDir });
if (build.status !== 0) {
  console.error('SMOKE_BUILD_FAILED');
  process.exit(1);
}

const userData = fs.mkdtempSync(path.join(os.tmpdir(), 'drabbit-smoke-'));
const entry = path.join(appDir, 'dist', 'main', 'main.js');
const useXvfb = process.platform === 'linux' && !process.env.DISPLAY;
const cmd = useXvfb ? 'xvfb-run' : electronBin;
const args = useXvfb ? ['-a', electronBin, '--no-sandbox', entry] : ['--no-sandbox', entry];

const child = spawn(cmd, args, {
  cwd: appDir,
  env: { ...process.env, DRABBIT_SMOKE: '1', DRABBIT_USER_DATA: userData },
});
let out = '';
child.stdout.on('data', (d) => {
  out += d;
  process.stdout.write(d);
});
child.stderr.on('data', (d) => {
  out += d;
  process.stderr.write(d);
});

const timeout = setTimeout(() => {
  console.error('SMOKE_TIMEOUT: no SMOKE_OK within 60s');
  child.kill('SIGKILL');
  process.exit(1);
}, 60000);

child.on('exit', (code) => {
  clearTimeout(timeout);
  if (out.includes('SMOKE_OK')) {
    console.log('SMOKE_OK confirmed — Electron launched and both windows loaded.');
    process.exit(0);
  }
  console.error(`SMOKE_FAILED: electron exited (${code}) without SMOKE_OK`);
  process.exit(1);
});
child.on('error', (err) => {
  clearTimeout(timeout);
  console.error(`SMOKE_ENV_MISSING: could not launch electron: ${err.message}`);
  process.exit(2);
});
