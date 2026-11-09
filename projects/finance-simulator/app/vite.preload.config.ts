import { defineConfig } from 'vite';

// Preload bundle build (Codex PR #8, round 1).
//
// electron/main.ts runs the preload with `sandbox: true`, and a sandboxed
// preload cannot use Node's module loader for relative modules — it may
// only require `electron` (and a few builtins). The previous plain-tsc
// build preserved preload.ts's local imports as
// `require("../shared/ipc-channels")`, so the preload threw before
// `contextBridge.exposeInMainWorld` ran and `window.sim` never existed in
// the production app. This config bundles the preload and its local
// imports into ONE script with `electron` kept external, emitted next to
// main.js as dist/electron/preload.js (the path main.ts already loads).
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
