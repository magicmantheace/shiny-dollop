import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    testTimeout: 20000,
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
          globals: true,
          include: ['tests/ui/**/*.test.tsx', 'tests/ui/**/*.test.ts'],
          setupFiles: ['tests/ui/setup.ts'],
        },
      },
    ],
  },
});
