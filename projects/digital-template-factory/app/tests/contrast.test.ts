/**
 * Contrast checker tests. Asserts the canonical #000 on #fff = 21:1 ratio.
 */
import { describe, expect, it } from 'vitest';
import {
  checkContrast,
  contrastRatio,
  relativeLuminance,
} from '../electron/main/validators/contrast';
import type { ThemeTokens } from '../shared/types';

function tokens(overrides: Partial<ThemeTokens> = {}): ThemeTokens {
  return {
    bg: '#ffffff',
    text: '#000000',
    accent: '#000000',
    headingFont: 'Georgia, serif',
    bodyFont: 'Arial, sans-serif',
    spacing: 16,
    ...overrides,
  };
}

describe('contrastRatio', () => {
  it('computes the canonical black-on-white ratio of 21:1', () => {
    expect(contrastRatio('#000000', '#ffffff')).toBeCloseTo(21, 5);
    expect(contrastRatio('#000', '#fff')).toBeCloseTo(21, 5);
  });

  it('is symmetric and equals 1 for identical colors', () => {
    expect(contrastRatio('#123456', '#123456')).toBeCloseTo(1, 5);
    expect(contrastRatio('#ffffff', '#000000')).toBeCloseTo(21, 5);
  });

  it('returns undefined for unparsable colors', () => {
    expect(contrastRatio('red', '#ffffff')).toBeUndefined();
    expect(contrastRatio('#gggggg', '#ffffff')).toBeUndefined();
  });
});

describe('relativeLuminance', () => {
  it('gives 0 for black and 1 for white', () => {
    expect(relativeLuminance('#000000')).toBeCloseTo(0, 5);
    expect(relativeLuminance('#ffffff')).toBeCloseTo(1, 5);
  });
});

describe('checkContrast', () => {
  it('passes a known-good dark-on-light theme', () => {
    expect(checkContrast(tokens())).toEqual([]);
  });

  it('fails light grey text on white and names the token', () => {
    expect(checkContrast(tokens({ text: '#cccccc' }))).toEqual(['text']);
  });

  it('fails a low-contrast accent used as text', () => {
    expect(checkContrast(tokens({ accent: '#eeeeee' }))).toEqual(['accent']);
  });

  it('reports both failing tokens', () => {
    expect(
      checkContrast(tokens({ text: '#dddddd', accent: '#dddddd' })),
    ).toEqual(['text', 'accent']);
  });

  it('treats unparsable colors as failures', () => {
    expect(checkContrast(tokens({ text: 'not-a-color' }))).toEqual(['text']);
  });

  it('passes the bundled invoice default tokens', () => {
    expect(
      checkContrast(
        tokens({ text: '#1a1a1a', accent: '#1d4ed8' }),
      ),
    ).toEqual([]);
  });
});
