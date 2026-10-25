import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    testTimeout: 15000,
    pool: 'forks',
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
          name: 'ui',
          environment: 'jsdom',
          include: ['tests/ui/**/*.test.tsx', 'tests/ui/**/*.test.ts'],
          setupFiles: ['tests/ui/setup.ts'],
        },
      },
    ],
  },
});
