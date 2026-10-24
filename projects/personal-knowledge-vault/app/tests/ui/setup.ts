import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterEach } from 'vitest';

// @testing-library/react only auto-cleans when the framework exposes a
// global afterEach. This project imports vitest APIs explicitly, so register
// cleanup manually to keep each UI test hermetic.
afterEach(() => {
  cleanup();
});
