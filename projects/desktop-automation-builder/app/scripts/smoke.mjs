/**
 * smoke — runs the packaged main process under Xvfb and expects SMOKE_OK.
 * Run `npm run build` first. Exits non-zero on any failure.
 */
import { spawnSync } from 'node:child_process';
import { createRequire } from 'node:module';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const electronBin = require('electron'); // path to the electron binary
const appDir = fileURLToPath(new URL('..', import.meta.url));

if (!existsSync(new URL('../dist/electron/main/main.js', import.meta.url))) {
  console.error('SMOKE FAIL: dist/electron/main/main.js missing — run `npm run build` first.');
  process.exit(1);
}

const res = spawnSync('xvfb-run', ['-a', electronBin, appDir, '--no-sandbox', '--dab-smoke'], {
  encoding: 'utf8',
  timeout: 120_000,
});

process.stdout.write(res.stdout ?? '');
process.stderr.write(res.stderr ?? '');

if (res.error) {
  console.error(`SMOKE FAIL: could not launch electron under xvfb: ${res.error.message}`);
  process.exit(1);
}
if (res.status !== 0 || !(res.stdout ?? '').includes('SMOKE_OK')) {
  console.error(`SMOKE FAIL: exit code ${res.status}, SMOKE_OK not printed.`);
  process.exit(1);
}
console.log('SMOKE PASS: packaged main printed SMOKE_OK under xvfb');
