import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterEach } from 'vitest';

afterEach(() => {
  cleanup();
  // Remove the fake window.lacc between tests so each test installs its own.
  if ('lacc' in window) {
    delete (window as unknown as Record<string, unknown>).lacc;
  }
});
