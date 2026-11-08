/**
 * Synthetic fixtures for backend tests. No real business data.
 */
import type { BusinessProfile, BusinessType, Site } from '../../shared/types.js';

export const INJECTION = '<img src=x onerror=alert(1)>';

export function makeProfile(overrides: Partial<BusinessProfile> = {}): BusinessProfile {
  return {
    name: 'Acme Test Co.',
    tagline: 'Testing tagline for fixtures.',
    about: 'A synthetic business used only in automated tests.',
    contact: {
      phone: '555-010-2030',
      email: 'hello@example.com',
      address: '123 Fixture Lane, Testville, TS 12345',
      website: 'https://acme-test.example.com',
    },
    hours: { label: 'Hours', lines: ['Mon–Fri: 9am–5pm', 'Sat: 10am–2pm'] },
    services: [
      { title: 'Service One', description: 'First synthetic service.' },
      { title: 'Service Two', description: 'Second synthetic service.' },
    ],
    menuSections: [
      {
        name: 'Starters',
        items: [
          { name: 'Test Soup', description: 'A synthetic soup.', price: '$9.99' },
          { name: 'Test Salad', description: 'A synthetic salad.', price: '$7.50' },
        ],
      },
    ],
    social: [{ label: 'Example', url: 'https://example.com/acme' }],
    seo: { title: 'Acme Test Co. — Fixtures', description: 'Synthetic SEO description for tests.' },
    ...overrides,
  };
}

/** Profile where every text field carries an XSS payload. */
export function makeInjectionProfile(): BusinessProfile {
  const x = INJECTION;
  return {
    name: x,
    tagline: x,
    about: x,
    contact: { phone: x, email: x, address: x, website: x },
    hours: { label: x, lines: [x, x] },
    services: [{ title: x, description: x }],
    menuSections: [{ name: x, items: [{ name: x, description: x, price: x }] }],
    social: [{ label: x, url: x }],
    seo: { title: x, description: x },
  };
}

export function makeSite(overrides: Partial<Site> = {}): Site {
  return {
    id: 'site-fixture-1',
    name: 'Acme Test Co.',
    businessType: 'trades' as BusinessType,
    themeId: 'trades',
    updatedAt: '2026-01-01T00:00:00.000Z',
    profile: makeProfile(),
    ...overrides,
  };
}
