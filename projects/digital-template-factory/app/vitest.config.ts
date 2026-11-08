import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    // Two projects: Worker A's backend tests (node) and Worker B's
    // renderer UI tests (jsdom, hermetic window.dtf mocks).
    projects: [
      {
        test: {
          name: 'backend',
          environment: 'node',
          include: ['tests/**/*.test.ts'],
        },
      },
      {
        test: {
          name: 'renderer',
          environment: 'jsdom',
          include: ['src/**/*.test.{ts,tsx}'],
          setupFiles: ['./src/test-setup.ts'],
        },
      },
    ],
  },
});
