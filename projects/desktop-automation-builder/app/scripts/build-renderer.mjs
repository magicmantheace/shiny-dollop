/**
 * build:renderer — runs `vite build` when the renderer slice is present.
 *
 * Worker B owns app/src/** and app/index.html and works on this branch in
 * parallel; until their entry file lands there is nothing to bundle, so we
 * skip with a clear notice instead of failing the backend build. Once
 * index.html exists the real Vite build runs and any failure is fatal.
 */
import { existsSync } from 'node:fs';
import { spawnSync } from 'node:child_process';

if (!existsSync(new URL('../index.html', import.meta.url))) {
  console.log('build:renderer: SKIP — app/index.html not present yet (renderer slice pending).');
  process.exit(0);
}

const res = spawnSync('npx', ['vite', 'build'], { stdio: 'inherit', shell: process.platform === 'win32' });
process.exit(res.status ?? 1);
