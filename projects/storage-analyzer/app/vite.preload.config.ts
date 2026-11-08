import { defineConfig } from 'vite';

// Preload bundle build.
//
// electron/main/index.ts runs the preload with `sandbox: true`, and a
// sandboxed preload cannot use Node's module loader for relative modules —
// it may only require `electron` (and a few builtins). The previous plain-tsc
// build preserved preload/index.ts's local import as
// `require("../../shared/ipc-channels")`, so the preload threw
// "module not found: ../../shared/ipc-channels" before
// `contextBridge.exposeInMainWorld` ran and `window.storageAnalyzer` never
// existed in the real app — the UI booted dead. (Same defect proven live on
// projects/universal-game-launcher during the 2026-11-04 Windows validation
// on the owner's PC; this app was flagged by the follow-up source sweep —
// identical tsc preload build, identical value import, `sandbox: true`.)
// This config bundles the preload and its local imports into ONE script
// with `electron` kept external, emitted at dist/electron/preload/index.js —
// the path main already loads. Mirrors
// projects/finance-simulator's vite.preload.config.ts.
export default defineConfig({
  build: {
    outDir: 'dist/electron/preload',
    emptyOutDir: false,
    sourcemap: false,
    minify: false,
    target: 'es2022',
    lib: {
      entry: 'electron/preload/index.ts',
      formats: ['cjs'],
      fileName: () => 'index.js',
    },
    rollupOptions: {
      external: ['electron'],
    },
  },
});
