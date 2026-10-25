import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

const here = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  plugins: [react()],
  // Keep this config self-contained: resolve everything relative to the
  // renderer folder, not the app root (whose own vitest.config.ts covers
  // app/tests with a node environment).
  root: here,
  resolve: {
    // Mirrors the @shared alias from app/tsconfig.json so tests resolve the
    // shared contract exactly like the real build does.
    alias: {
      '@shared': path.join(here, '..', 'shared'),
    },
  },
  test: {
    // Globals on: @testing-library/react auto-cleanup hooks into the global
    // afterEach, and without it renders accumulate across tests in a file.
    globals: true,
    environment: 'jsdom',
    setupFiles: [path.join(here, 'tests', 'setup.ts')],
    include: ['tests/**/*.test.{ts,tsx}'],
  },
});
