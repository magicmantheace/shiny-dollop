import { defineConfig } from 'vitest/config';

/**
 * Worker B (renderer UI) owns this config.
 * Worker A (backend): add a second project here for node-side backend tests
 * (`environment: 'node', include: ['tests/backend/**\/*.test.ts']`) when the
 * backend test suite lands.
 */
export default defineConfig({
  test: {
    projects: [
      {
        test: {
          name: 'renderer',
          environment: 'jsdom',
          include: ['tests/renderer/**/*.test.{ts,tsx}'],
          setupFiles: ['./src/test-setup.ts'],
        },
      },
      {
        // Worker A (backend): node-side tests for themes, validators,
        // exporter, SQLite store, IPC handlers and the preload contract.
        test: {
          name: 'backend',
          environment: 'node',
          include: ['tests/backend/**/*.test.ts'],
        },
      },
    ],
  },
});
