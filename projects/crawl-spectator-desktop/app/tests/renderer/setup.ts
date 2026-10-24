import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterEach } from 'vitest';

afterEach(() => {
  cleanup();
  // Remove the fake window.spectator between tests so each test installs its own.
  if ('spectator' in window) {
    delete (window as unknown as Record<string, unknown>).spectator;
  }
});
