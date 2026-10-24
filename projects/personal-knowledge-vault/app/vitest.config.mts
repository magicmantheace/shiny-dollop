import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    // Worker A (backend) + Worker B (renderer UI) suites.
    include: ['tests/backend/**/*.test.ts', 'tests/ui/**/*.{test,spec}.{ts,tsx}'],
    environment: 'node',
    environmentMatchGlobs: [['**/tests/ui/**', 'jsdom']],
    setupFiles: ['./tests/ui/setup.ts'],
    testTimeout: 15000,
  },
});
