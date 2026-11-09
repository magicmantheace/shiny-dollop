import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    include: ['tests/backend/**/*.test.ts', 'tests/ui/**/*.{test,spec}.{ts,tsx}'],
    environment: 'node',
    environmentMatchGlobs: [['**/tests/ui/**', 'jsdom']],
    setupFiles: ['./tests/ui/setup.ts'],
    testTimeout: 15000,
  },
});
