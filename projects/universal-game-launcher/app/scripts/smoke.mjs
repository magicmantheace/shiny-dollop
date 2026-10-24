#!/usr/bin/env node
/**
 * Headless smoke test: production-builds the app, then opens the real
 * Electron window under xvfb (Linux) and expects the SMOKE_OK marker.
 * GUI/Windows-only behaviors are NOT verified here — only that the packaged
 * production bundle boots to a real native window.
 */
import { spawnSync, spawn } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.dirname(fileURLToPath(import.meta.url));
const appDir = path.join(root, '..');

function sh(cmd, args) {
  const r = spawnSync(cmd, args, { cwd: appDir, stdio: 'inherit', shell: false });
  if (r.status !== 0) {
    console.error(`[smoke] FAILED: ${cmd} ${args.join(' ')}`);
    process.exit(1);
  }
}

console.log('[smoke] building production bundle…');
sh('npm', ['run', 'build', '--silent']);

const electronBin = path.join(
  appDir,
  'node_modules',
  '.bin',
  process.platform === 'win32' ? 'electron.cmd' : 'electron',
);
const entry = path.join(appDir, 'dist', 'electron', 'main', 'index.js');

const useXvfb = process.platform === 'linux';
const cmd = useXvfb ? 'xvfb-run' : electronBin;
const args = useXvfb
  ? ['-a', electronBin, '--no-sandbox', entry]
  : ['--no-sandbox', entry];

console.log('[smoke] launching Electron (UGL_SMOKE=1)…');
const child = spawn(cmd, args, {
  cwd: appDir,
  env: { ...process.env, UGL_SMOKE: '1' },
  stdio: ['ignore', 'pipe', 'pipe'],
});

let sawOk = false;
let output = '';
child.stdout.on('data', (d) => {
  const s = d.toString();
  output += s;
  if (s.includes('SMOKE_OK')) sawOk = true;
});
child.stderr.on('data', (d) => {
  output += d.toString();
});

const timeout = setTimeout(() => {
  try {
    child.kill('SIGKILL');
  } catch {
    // ignore
  }
}, 60000);

child.on('exit', () => {
  clearTimeout(timeout);
  if (sawOk) {
    console.log('[smoke] PASS: production bundle opened a real window (SMOKE_OK).');
    process.exit(0);
  }
  console.error('[smoke] FAIL: SMOKE_OK marker not seen.');
  console.error(output.slice(-3000));
  process.exit(1);
});
