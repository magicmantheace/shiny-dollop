import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    // Backend suite (Worker A). Renderer suite (Worker B) lives in
    // tests/renderer/** and runs under jsdom once Worker B adds it.
    include: ['tests/backend/**/*.test.ts', 'tests/renderer/**/*.{test,spec}.{ts,tsx}'],
    environment: 'node',
    environmentMatchGlobs: [['**/tests/renderer/**', 'jsdom']],
    testTimeout: 30000,
  },
});
