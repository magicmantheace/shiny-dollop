import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterEach } from 'vitest';

// vitest runs without globals here, so register RTL cleanup manually.
afterEach(() => {
  cleanup();
});
