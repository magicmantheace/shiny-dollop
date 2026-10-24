/**
 * Smoke check: typecheck + unit tests. Run with `npm run smoke`.
 */
import { execSync } from 'node:child_process';

execSync('npm run typecheck', { stdio: 'inherit' });
execSync('npm run test -- --run', { stdio: 'inherit' });
console.log('smoke: OK');
