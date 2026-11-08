import { defineConfig } from 'vite';

// Preload bundle build.
//
// electron/main.ts runs the preload with `sandbox: true`, and a sandboxed
// preload cannot use Node's module loader for relative modules — it may
// only require `electron` (and a few builtins). The previous plain-tsc
// build preserved preload.ts's value import of the IPC channel constants
// as `require("../shared/types")`, so the preload threw
// "module not found: ../shared/types" before
// `contextBridge.exposeInMainWorld` ran and `window.pkv` never existed in
// the real app (the same defect proven live on the Universal Game
// Launcher, 2026-11-04; the unit tests use a hermetic `window.pkv` mock
// and the boot smoke never exercised the sandboxed preload). This config
// bundles the preload and its local imports into ONE script with
// `electron` kept external, emitted next to main.js as
// dist/electron/preload.js (the path main.ts already loads).
// shared/types.ts is self-contained — its only runtime export is the
// PkvChannels constant and it imports nothing — so the bundle needs no
// other externals. Mirrors projects/finance-simulator's
// vite.preload.config.ts.
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
