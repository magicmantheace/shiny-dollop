#!/usr/bin/env node
// Dev launcher: builds renderer in watch mode via vite dev server and starts Electron against it.
import { spawn } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const appDir = path.join(__dirname, '..');

const vite = spawn('npx', ['vite', '--port', '5174'], { cwd: appDir, stdio: 'inherit', shell: true });
await new Promise((r) => setTimeout(r, 4000));

const electron = spawn('npx', ['tsc', '-p', 'tsconfig.main.json'], { cwd: appDir, stdio: 'inherit', shell: true });
electron.on('exit', () => {
  const run = spawn(
    'npx',
    ['electron', '.', '--enable-logging'],
    {
      cwd: appDir,
      stdio: 'inherit',
      shell: true,
      env: { ...process.env, VCC_DEV_URL: 'http://localhost:5174' },
    },
  );
  run.on('exit', () => {
    vite.kill();
    process.exit(0);
  });
});
