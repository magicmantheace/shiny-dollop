/**
 * Validator tests: every named error code, plus the blocking rule.
 */
import { describe, expect, it } from 'vitest';
import {
  hasBlockingErrors,
  validateAssets,
  validateContrast,
  validateExport,
  validateHtml,
  validateLinks,
  validateProfile,
} from '../../electron/main/validate.js';
import { getTheme } from '../../electron/main/themes/index.js';
import { makeProfile } from './fixtures.js';
import type { BusinessProfile } from '../../shared/types.js';

function emptyProfile(): BusinessProfile {
  return {
    name: '',
    tagline: '',
    about: '',
    contact: { phone: '', email: '', address: '', website: '' },
    hours: { label: '', lines: [] },
    services: [],
    menuSections: [],
    social: [],
    seo: { title: '', description: '' },
  };
}

describe('validateProfile', () => {
  it('passes a complete profile with no issues', () => {
    expect(validateProfile(makeProfile())).toEqual([]);
  });

  it('emits FIELD_REQUIRED for every missing required field', () => {
    const codes = validateProfile(emptyProfile()).map((i) => i.code);
    expect(codes).toContain('FIELD_REQUIRED:name');
    expect(codes).toContain('FIELD_REQUIRED:contact.email-or-phone');
    expect(codes).toContain('FIELD_REQUIRED:services');
    expect(codes).toContain('FIELD_REQUIRED:seo.title');
    expect(codes).toContain('FIELD_REQUIRED:seo.description');
  });

  it('accepts phone alone as the contact method', () => {
    const p = emptyProfile();
    p.contact.phone = '555-010-2030';
    const codes = validateProfile(p).map((i) => i.code);
    expect(codes).not.toContain('FIELD_REQUIRED:contact.email-or-phone');
  });

  it('accepts email alone as the contact method', () => {
    const p = emptyProfile();
    p.contact.email = 'a@example.com';
    const codes = validateProfile(p).map((i) => i.code);
    expect(codes).not.toContain('FIELD_REQUIRED:contact.email-or-phone');
  });
});

describe('validateHtml', () => {
  const good = '<!DOCTYPE html><html><head><title>t</title></head><body><main><p>x</p></main></body></html>';

  it('passes well-formed HTML', () => {
    expect(validateHtml('index.html', good)).toEqual([]);
  });

  it('flags a missing <main> landmark', () => {
    const codes = validateHtml('index.html', good.replace('<main>', '<div>').replace('</main>', '</div>')).map(
      (i) => i.code,
    );
    expect(codes).toContain('HTML_INVALID:missing-main');
  });

  it('flags unbalanced tags', () => {
    const codes = validateHtml('index.html', good.replace('</p>', '')).map((i) => i.code);
    expect(codes).toContain('HTML_INVALID:unbalanced-p');
  });

  it('flags stray closing tags', () => {
    const codes = validateHtml('index.html', good + '</span>').map((i) => i.code);
    expect(codes).toContain('HTML_INVALID:unbalanced-span');
  });

  it('flags <script> tags', () => {
    const codes = validateHtml(
      'index.html',
      good.replace('</body>', '<script>alert(1)</script></body>'),
    ).map((i) => i.code);
    expect(codes).toContain('HTML_INVALID:script-present');
  });
});

describe('validateLinks', () => {
  it('passes when every internal link resolves', () => {
    const files = {
      'index.html': '<a href="services.html">S</a><a href="https://example.com">E</a><a href="mailto:a@b.c">M</a>',
      'services.html': '<a href="index.html">H</a>',
    };
    expect(validateLinks(files)).toEqual([]);
  });

  it('emits LINK_BROKEN for an unresolvable internal href', () => {
    const files = { 'index.html': '<a href="missing.html">M</a>' };
    const issues = validateLinks(files);
    expect(issues.map((i) => i.code)).toContain('LINK_BROKEN:missing.html');
  });
});

describe('validateAssets', () => {
  it('emits ASSET_MISSING for a referenced image that is not exported', () => {
    const files = { 'index.html': '<img src="photos/shop.png" alt="shop">' };
    const issues = validateAssets(files);
    expect(issues.map((i) => i.code)).toContain('ASSET_MISSING:photos/shop.png');
  });

  it('passes when the referenced image is exported', () => {
    const files = {
      'index.html': '<img src="photos/shop.png" alt="shop">',
      'photos/shop.png': 'binary',
    };
    expect(validateAssets(files)).toEqual([]);
  });
});

describe('validateContrast', () => {
  it('passes the shipped theme tokens', () => {
    for (const id of ['trades', 'author', 'restaurant', 'localbiz']) {
      expect(validateContrast(getTheme(id)!.tokens), `theme ${id}`).toEqual([]);
    }
  });

  it('emits CONTRAST_FAIL for a low-contrast pair', () => {
    const issues = validateContrast([{ name: 'bad-pair', fg: '#777777', bg: '#888888' }]);
    expect(issues.map((i) => i.code)).toContain('CONTRAST_FAIL:bad-pair');
  });
});

describe('validateExport + blocking', () => {
  it('passes a fully rendered fixture site end to end', () => {
    const theme = getTheme('trades')!;
    const profile = makeProfile();
    const issues = validateExport(profile, theme.renderSite(profile).files, theme);
    expect(issues).toEqual([]);
    expect(hasBlockingErrors(issues)).toBe(false);
  });

  it('blocks export when required fields are missing', () => {
    const theme = getTheme('trades')!;
    const profile = emptyProfile();
    const issues = validateExport(profile, theme.renderSite(profile).files, theme);
    expect(hasBlockingErrors(issues)).toBe(true);
    expect(issues.some((i) => i.code === 'FIELD_REQUIRED:name')).toBe(true);
  });
});
