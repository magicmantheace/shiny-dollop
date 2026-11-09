// Builds a portable release zip: dist/ bundled with the Electron runtime.
// Run: npm run pack   (runs `vite build` first)
import { mkdirSync, rmSync, cpSync, existsSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { execFileSync } from 'node:child_process';

const here = dirname(fileURLToPath(import.meta.url));
const appDir = join(here, '..');
const distDir = join(appDir, 'dist');
const releaseDir = join(appDir, 'release');

if (!existsSync(distDir)) {
  console.error('dist/ not found — run `npm run build` first.');
  process.exit(1);
}

mkdirSync(releaseDir, { recursive: true });

const electronDist = join(appDir, 'node_modules', 'electron', 'dist');
const stageDir = join(releaseDir, 'stage');
rmSync(stageDir, { recursive: true, force: true });
mkdirSync(stageDir, { recursive: true });

// Electron runtime
execFileSync('bash', ['-c', `cp -r "${electronDist}"/. "${stageDir}"/`], { stdio: 'inherit' });

// App bundle as the Electron "app" directory
const appResources = join(stageDir, 'resources', 'app');
mkdirSync(appResources, { recursive: true });
cpSync(distDir, join(appResources, 'dist'), { recursive: true });
cpSync(join(appDir, 'package.json'), join(appResources, 'package.json'));

// Zip it
const zipName = `game-metadata-manager-1.0.0-portable-${process.platform}-${process.arch}.zip`;
const zipPath = join(releaseDir, zipName);
rmSync(zipPath, { force: true });
execFileSync('bash', ['-c', `cd "${stageDir}" && zip -qr "${zipPath}" .`], { stdio: 'inherit' });
rmSync(stageDir, { recursive: true, force: true });

console.log(`portable release: ${zipPath}`);
