import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    environment: 'jsdom',
    globals: true,
    include: ['tests-ui/**/*.test.{ts,tsx}'],
    setupFiles: ['./tests-ui/setup.ts'],
    testTimeout: 10000,
  },
});
