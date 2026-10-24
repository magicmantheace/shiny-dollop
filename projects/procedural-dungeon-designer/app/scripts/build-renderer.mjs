import { existsSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
if (!existsSync(new URL('../index.html', import.meta.url))) {
  console.log('build:renderer: SKIP — app/index.html not present yet (renderer slice pending).');
  process.exit(0);
}
const res = spawnSync('npx', ['vite', 'build'], { stdio: 'inherit', shell: process.platform === 'win32' });
process.exit(res.status ?? 1);
