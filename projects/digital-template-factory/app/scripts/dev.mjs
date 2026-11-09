/**
 * Dev launcher: builds main/preload, starts vite, then electron.
 * (Backend milestone: minimal stub — full dev loop lands with the
 * renderer integration.)
 */
import { spawn } from 'node:child_process';

const vite = spawn('npx', ['vite', '--port', '5175'], {
  stdio: 'inherit',
  shell: true,
  env: { ...process.env, VITE_DEV_SERVER_URL: 'http://localhost:5175' },
});

vite.on('exit', (code) => process.exit(code ?? 0));
process.on('SIGINT', () => vite.kill('SIGINT'));
