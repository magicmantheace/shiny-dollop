// Filesystem layout of the built app, resolved from the main-process
// directory (`dist/electron/main` after `tsc -p tsconfig.main.json`).
//
//   dist/
//     electron/main/main.js     <- __dirname of the main process
//     electron/preload/preload.js
//     renderer/index.html       <- Vite `build.outDir` (see vite.config.ts)
//
// Pure helpers (no Electron imports) so the layout is unit-testable.
import { join } from 'node:path';

/** Compiled preload script, one level up from the main-process directory. */
export function preloadScriptPath(mainDir: string): string {
  return join(mainDir, '..', 'preload', 'preload.js');
}

/**
 * Renderer entry point. Vite writes it to `dist/renderer`, which is TWO
 * levels above `dist/electron/main` — not one. Resolving it with a single
 * `..` lands in the non-existent `dist/electron/renderer` and the window
 * opens blank.
 */
export function rendererIndexPath(mainDir: string): string {
  return join(mainDir, '..', '..', 'renderer', 'index.html');
}
