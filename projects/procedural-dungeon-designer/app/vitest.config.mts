import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    include: ['tests/backend/**/*.test.ts', 'tests/renderer/**/*.{test,spec}.{ts,tsx}'],
    environment: 'node',
    environmentMatchGlobs: [['**/tests/renderer/**', 'jsdom']],
    testTimeout: 30000,
  },
});
