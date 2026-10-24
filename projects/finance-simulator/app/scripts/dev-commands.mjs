/**
 * Launch specs for scripts/dev.mjs.
 *
 * Every tool (tsc, Vite, Electron) is launched through its JavaScript
 * entry point with the current Node executable instead of through the
 * platform command shim (`npx`, `node_modules/.bin/electron`, ...).
 * On Windows those shims are `.cmd` files, and Node's child_process
 * cannot spawn a `.cmd` file without `shell: true` — `npm run dev`
 * failed there with ENOENT/EINVAL. The JS entry points below are the
 * exact files those shims forward to (`typescript/bin/tsc`,
 * `vite/bin/vite.js`, `electron/cli.js` — the `.bin/electron` shim is
 * itself just a wrapper around cli.js), so behaviour is unchanged on
 * POSIX and now works on Windows without a shell.
 */
import path from 'node:path';

function nodeEntry(appDir, entrySegments, args, execPath) {
  return {
    command: execPath,
    args: [path.join(appDir, 'node_modules', ...entrySegments), ...args],
  };
}

/** tsc watch build for one tsconfig (main / preload). */
export function tscWatchCommand(appDir, tsconfig, execPath = process.execPath) {
  return nodeEntry(
    appDir,
    ['typescript', 'bin', 'tsc'],
    ['-p', tsconfig, '--watch', '--preserveWatchOutput'],
    execPath,
  );
}

/** Vite renderer dev server on the given (strict) port. */
export function viteCommand(appDir, port, execPath = process.execPath) {
  return nodeEntry(
    appDir,
    ['vite', 'bin', 'vite.js'],
    ['--port', String(port), '--strictPort'],
    execPath,
  );
}

/** Electron for the built main entry, with caller-supplied extra args. */
export function electronCommand(appDir, entry, extraArgs = [], execPath = process.execPath) {
  return nodeEntry(appDir, ['electron', 'cli.js'], [...extraArgs, entry], execPath);
}
