/**
 * Bundle the Electron main process and preload with esbuild.
 * Output: dist/main/main.js, dist/main/preload.js (CommonJS for Electron).
 */
import { build } from 'esbuild';
import { mkdirSync } from 'node:fs';

mkdirSync('dist/main', { recursive: true });

await build({
  entryPoints: ['electron/main/main.ts'],
  bundle: true,
  platform: 'node',
  format: 'cjs',
  target: 'node22',
  outfile: 'dist/main/main.js',
  external: ['electron'],
  sourcemap: false,
  logLevel: 'info',
});

await build({
  entryPoints: ['electron/preload.ts'],
  bundle: true,
  platform: 'node',
  format: 'cjs',
  target: 'node22',
  outfile: 'dist/main/preload.js',
  external: ['electron'],
  sourcemap: false,
  logLevel: 'info',
});

console.log('main + preload bundled to dist/main/');
