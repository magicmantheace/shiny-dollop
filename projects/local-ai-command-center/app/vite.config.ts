import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  root: '.',
  base: './',
  build: {
    outDir: 'dist/renderer',
    emptyOutDir: true,
    sourcemap: false,
  },
  server: {
    port: 5181,
    strictPort: true,
  },
  // Test config lives in vitest.config.mts (shared by backend + renderer suites).
});
