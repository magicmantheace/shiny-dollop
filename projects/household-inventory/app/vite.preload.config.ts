import { defineConfig } from 'vite';

// Preload bundle build.
//
// electron/main.ts runs the preload with `sandbox: true`, and a sandboxed
// preload cannot use Node's module loader for relative modules — it may
// only require `electron` (and a few builtins). The previous plain-tsc
// build preserved preload.ts's local import as
// `require("../shared/ipc-channels")`, so the preload threw
// "module not found: ../shared/ipc-channels" before
// `contextBridge.exposeInMainWorld` ran and `window.inv` never existed in
// the production app. (Same defect proven live on the Universal Game
// Launcher's packaged build during the 2026-11-04 Windows validation,
// PR #30; this app's copy was confirmed by source inspection — identical
// sandbox setting, identical tsc-preserved relative require.) This config
// bundles the preload and its local imports into ONE script with
// `electron` kept external, emitted next to main.js as
// dist/electron/preload.js (the path main.ts already loads). Mirrors
// projects/finance-simulator's vite.preload.config.ts.
export default defineConfig({
  build: {
    outDir: 'dist/electron',
    emptyOutDir: false,
    sourcemap: false,
    minify: false,
    target: 'es2022',
    lib: {
      entry: 'electron/preload.ts',
      formats: ['cjs'],
      fileName: () => 'preload.js',
    },
    rollupOptions: {
      external: ['electron'],
    },
  },
});
