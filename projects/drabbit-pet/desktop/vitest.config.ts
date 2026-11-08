import { defineConfig } from 'vitest/config';

// Headless unit tests only: save store, tick service, roaming planner,
// IPC action mapping, visual-state derivation. The Electron GUI is not
// exercised here (owner-PC verification; see docs/TEST_PLAN.md).
export default defineConfig({
  test: {
    environment: 'node',
    include: ['tests/**/*.test.ts'],
  },
});
