import { defineConfig } from 'vite';

/**
 * Preload bundle config. The preload runs sandboxed (sandbox: true), and a
 * sandboxed preload may only require() a tiny allowlist of built-ins
 * (electron, events, timers, url) — it cannot load local CommonJS files.
 * The old `tsc -p tsconfig.preload.json` output kept the runtime import of
 * ../../shared/ipc-channels as a separate require(), so the preload threw
 * before contextBridge could expose window.concreteOps. Bundling with Vite
 * inlines the shared channel constants into a single self-contained script
 * whose only require is 'electron'.
 */
export default defineConfig({
  build: {
    outDir: 'dist/electron/preload',
    emptyOutDir: true,
    sourcemap: false,
    minify: false,
    target: 'node18',
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
