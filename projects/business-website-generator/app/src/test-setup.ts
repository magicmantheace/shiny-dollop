import '@testing-library/jest-dom/vitest';
import { afterEach } from 'vitest';
import { cleanup } from '@testing-library/react';

// Vitest runs without globals here, so @testing-library/react's
// auto-cleanup does not register itself. Clean the DOM explicitly to keep
// every test hermetic.
afterEach(() => {
  cleanup();
});
