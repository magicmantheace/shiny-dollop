import { describe, expect, it } from 'vitest';
import { hasAiArt } from '../src/renderer/pet/visual-state.js';

describe('hasAiArt', () => {
  it('covers the persistent states for royal fur', () => {
    for (const anim of ['idle', 'hopping', 'eating', 'playing', 'sick', 'sleeping'] as const) {
      expect(hasAiArt('royal', anim)).toBe(true);
    }
  });

  it('leaves the uncovered states on the SVG', () => {
    for (const anim of ['egg', 'egg-ready', 'cleaning', 'healing', 'hatching', 'dead'] as const) {
      expect(hasAiArt('royal', anim)).toBe(false);
    }
  });

  it('is royal-only — every other fur stays on the SVG', () => {
    for (const fur of ['ember', 'meadow', 'sky', 'sunset', 'rainbow'] as const) {
      expect(hasAiArt(fur, 'idle')).toBe(false);
      expect(hasAiArt(fur, 'sleeping')).toBe(false);
    }
  });
});
