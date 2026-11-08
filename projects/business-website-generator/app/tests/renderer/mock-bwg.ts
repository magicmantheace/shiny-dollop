/**
 * Hermetic in-memory mock of the `window.bwg` API for renderer tests.
 *
 * No test may touch the real backend. The mock implements the full contract
 * with realistic behavior: profile merging, theme switching, page rendering
 * from the profile (HTML-escaped), and export validation that produces the
 * same named issue codes the real backend is expected to use.
 */
import type {
  BusinessProfile,
  BusinessProfilePatch,
  BusinessType,
  BwgApi,
  RenderedPage,
  Site,
  SiteSummary,
  ThemeInfo,
  ValidationIssue,
} from '../../shared/types';

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

export function cleanProfile(name: string): BusinessProfile {
  return {
    name,
    tagline: 'Quality you can trust',
    about: 'A fine local business serving the community since 2019.',
    contact: {
      phone: '+1 403-555-0123',
      email: 'hello@example.com',
      address: '123 Main St, Lethbridge, AB',
      website: 'https://example.com',
    },
    hours: { label: 'Hours', lines: ['Mon–Fri: 9am–5pm', 'Sat: 10am–2pm'] },
    services: [{ title: 'Consultation', description: 'Free first visit.' }],
    menuSections: [],
    social: [{ label: 'Facebook', url: 'https://facebook.com/example' }],
    seo: { title: 'Example Business | Lethbridge', description: 'A fine local business.' },
  };
}

export function restaurantProfile(name: string): BusinessProfile {
  const p = cleanProfile(name);
  p.menuSections = [
    {
      name: 'Mains',
      items: [{ name: 'Burger', description: 'Classic beef burger.', price: '$12.99' }],
    },
  ];
  return p;
}

const MOCK_THEMES: ThemeInfo[] = [
  {
    id: 'theme-workshop',
    name: 'Workshop',
    description: 'Bold, high-contrast layout for trades.',
    businessTypes: ['trades', 'localbiz'],
    pages: ['index.html', 'services.html', 'contact.html'],
  },
  {
    id: 'theme-solid',
    name: 'Solid',
    description: 'Dependable two-column layout for trades and local businesses.',
    businessTypes: ['trades', 'localbiz'],
    pages: ['index.html', 'services.html', 'contact.html'],
  },
  {
    id: 'theme-bistro',
    name: 'Bistro',
    description: 'Warm menu-first layout for restaurants.',
    businessTypes: ['restaurant'],
    pages: ['index.html', 'menu.html', 'contact.html'],
  },
  {
    id: 'theme-minimal',
    name: 'Minimal',
    description: 'Clean single-column layout for authors.',
    businessTypes: ['author', 'localbiz'],
    pages: ['index.html', 'about.html', 'contact.html'],
  },
];

export interface MockBwg extends BwgApi {
  calls: {
    list: number;
    create: { name: string; businessType: BusinessType; themeId: string }[];
    get: string[];
    updateProfile: { id: string; patch: BusinessProfilePatch }[];
    delete: string[];
    setTheme: { id: string; themeId: string }[];
    themesList: number;
    previewRender: string[];
    validate: string[];
    exportRun: { id: string; destDir: string }[];
    pickDirectory: number;
  };
  /** Override what dialog.pickDirectory() resolves with. */
  __setPickDirectoryResult: (dir: string | null) => void;
  /** Direct access to the in-memory sites for assertions. */
  __sites: Map<string, Site>;
}

function validateProfile(profile: BusinessProfile, businessType: BusinessType): ValidationIssue[] {
  const issues: ValidationIssue[] = [];
  if (profile.name.trim() === '') {
    issues.push({ code: 'SITE_NAME_MISSING', message: 'The site name is empty.', field: 'profile.name' });
  }
  if (profile.contact.email.trim() !== '' && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(profile.contact.email.trim())) {
    issues.push({
      code: 'CONTACT_EMAIL_INVALID',
      message: `Contact email "${profile.contact.email}" is not a valid email address.`,
      field: 'profile.contact.email',
    });
  }
  if (profile.contact.website.trim() !== '' && !/^https?:\/\/.+/.test(profile.contact.website.trim())) {
    issues.push({
      code: 'CONTACT_WEBSITE_INVALID',
      message: 'Contact website must start with http:// or https://.',
      field: 'profile.contact.website',
    });
  }
  if (profile.contact.phone.trim() !== '') {
    const digits = profile.contact.phone.replace(/\D/g, '');
    if (!/^[+\d(][\d\s().\-]*$/i.test(profile.contact.phone.trim()) || digits.length < 7) {
      issues.push({
        code: 'CONTACT_PHONE_INVALID',
        message: 'Contact phone number looks invalid.',
        field: 'profile.contact.phone',
      });
    }
  }
  profile.services.forEach((s, i) => {
    if (s.title.trim() === '') {
      issues.push({
        code: 'SERVICE_TITLE_MISSING',
        message: `Service ${i + 1} has no title.`,
        field: `profile.services[${i}].title`,
      });
    }
  });
  profile.social.forEach((s, i) => {
    if (s.url.trim() !== '' && !/^https?:\/\/.+/.test(s.url.trim())) {
      issues.push({
        code: 'SOCIAL_URL_INVALID',
        message: `Social link ${i + 1} must start with http:// or https://.`,
        field: `profile.social[${i}].url`,
      });
    }
  });
  if (businessType === 'restaurant') {
    if (profile.menuSections.length === 0) {
      issues.push({
        code: 'RESTAURANT_MENU_EMPTY',
        message: 'Restaurants need at least one menu section.',
        field: 'profile.menuSections',
      });
    }
    profile.menuSections.forEach((ms, i) => {
      if (ms.name.trim() === '') {
        issues.push({
          code: 'MENU_SECTION_NAME_MISSING',
          message: `Menu section ${i + 1} has no name.`,
          field: `profile.menuSections[${i}].name`,
        });
      }
      ms.items.forEach((item, j) => {
        if (item.name.trim() === '') {
          issues.push({
            code: 'MENU_ITEM_NAME_MISSING',
            message: `Item ${j + 1} in menu section ${i + 1} has no name.`,
            field: `profile.menuSections[${i}].items[${j}].name`,
          });
        }
      });
    });
  }
  if (profile.seo.title.trim() === '') {
    issues.push({ code: 'SEO_TITLE_MISSING', message: 'SEO title is empty.', field: 'profile.seo.title' });
  }
  return issues;
}

function renderPages(site: Site): RenderedPage[] {
  const theme = MOCK_THEMES.find((t) => t.id === site.themeId) ?? MOCK_THEMES[0]!;
  return theme.pages.map((path) => ({
    path,
    html:
      `<!doctype html><html><head><title>${escapeHtml(site.profile.seo.title)}</title></head>` +
      `<body data-theme="${escapeHtml(theme.id)}">` +
      `<h1>${escapeHtml(site.profile.name)}</h1>` +
      `<p>${escapeHtml(site.profile.tagline)}</p>` +
      `<p>${escapeHtml(path)}</p></body></html>`,
  }));
}

/**
 * Canonical patch merge (mirrors the backend): top-level scalars replace,
 * contact / hours / seo merge key-by-key, arrays replace wholesale when
 * present in the patch.
 */
function mergeProfile(base: BusinessProfile, patch: BusinessProfilePatch): BusinessProfile {
  return {
    name: patch.name ?? base.name,
    tagline: patch.tagline ?? base.tagline,
    about: patch.about ?? base.about,
    contact: { ...base.contact, ...patch.contact },
    hours: { ...base.hours, ...patch.hours },
    services: patch.services ?? base.services,
    menuSections: patch.menuSections ?? base.menuSections,
    social: patch.social ?? base.social,
    seo: { ...base.seo, ...patch.seo },
  };
}

let nextId = 1;

export function createMockBwg(): MockBwg {
  const sites = new Map<string, Site>();
  const now = new Date().toISOString();

  const seed = (summary: Omit<SiteSummary, 'id' | 'updatedAt'>, profile: BusinessProfile): Site => {
    const site: Site = {
      ...summary,
      id: `site-${nextId++}`,
      updatedAt: now,
      profile,
    };
    sites.set(site.id, site);
    return site;
  };

  seed(
    { name: 'Acme Plumbing', businessType: 'trades', themeId: 'theme-workshop' },
    cleanProfile('Acme Plumbing'),
  );
  seed(
    { name: 'Harbor Bistro', businessType: 'restaurant', themeId: 'theme-bistro' },
    restaurantProfile('Harbor Bistro'),
  );

  let pickDirectoryResult: string | null = '/mock/export/dir';

  const getSite = (id: string): Site => {
    const site = sites.get(id);
    if (!site) throw new Error(`Site not found: ${id}`);
    return site;
  };

  const mock: MockBwg = {
    calls: {
      list: 0,
      create: [],
      get: [],
      updateProfile: [],
      delete: [],
      setTheme: [],
      themesList: 0,
      previewRender: [],
      validate: [],
      exportRun: [],
      pickDirectory: 0,
    },
    __setPickDirectoryResult: (dir) => {
      pickDirectoryResult = dir;
    },
    __sites: sites,

    sites: {
      list: async () => {
        mock.calls.list += 1;
        return [...sites.values()].map(({ profile: _p, ...summary }) => summary);
      },
      create: async (input) => {
        mock.calls.create.push(input);
        return structuredClone(
          seed(
            { name: input.name, businessType: input.businessType, themeId: input.themeId },
            cleanProfile(input.name),
          ),
        );
      },
      get: async (id) => {
        mock.calls.get.push(id);
        const site = sites.get(id);
        return site ? structuredClone(site) : null;
      },
      updateProfile: async (id, patch) => {
        mock.calls.updateProfile.push({ id, patch });
        const site = getSite(id);
        const updated: Site = {
          ...site,
          profile: mergeProfile(site.profile, patch),
          updatedAt: new Date().toISOString(),
        };
        sites.set(id, updated);
        return structuredClone(updated);
      },
      delete: async (id) => {
        mock.calls.delete.push(id);
        return sites.delete(id);
      },
      setTheme: async (id, themeId) => {
        mock.calls.setTheme.push({ id, themeId });
        const site = getSite(id);
        const theme = MOCK_THEMES.find((t) => t.id === themeId);
        if (!theme) throw new Error(`Theme not found: ${themeId}`);
        if (!theme.businessTypes.includes(site.businessType)) {
          throw new Error(`Theme ${themeId} does not support ${site.businessType}`);
        }
        const updated: Site = { ...site, themeId, updatedAt: new Date().toISOString() };
        sites.set(id, updated);
        return structuredClone(updated);
      },
    },
    themes: {
      list: async () => {
        mock.calls.themesList += 1;
        return structuredClone(MOCK_THEMES);
      },
    },
    preview: {
      render: async (id) => {
        mock.calls.previewRender.push(id);
        return renderPages(getSite(id));
      },
    },
    export: {
      validate: async (id) => {
        mock.calls.validate.push(id);
        const site = getSite(id);
        const issues = validateProfile(site.profile, site.businessType);
        return { ok: issues.length === 0, issues };
      },
      run: async (id, destDir) => {
        mock.calls.exportRun.push({ id, destDir });
        const site = getSite(id);
        const issues = validateProfile(site.profile, site.businessType);
        if (issues.length > 0) {
          return { ok: false, destDir, files: [], issues };
        }
        const files = renderPages(site).map((p) => p.path);
        return { ok: true, destDir, files, issues: [] };
      },
    },
    dialog: {
      pickDirectory: async () => {
        mock.calls.pickDirectory += 1;
        return pickDirectoryResult;
      },
    },
  };

  return mock;
}

/** Installs a fresh mock on `window.bwg` and returns it for assertions. */
export function installMockBwg(): MockBwg {
  const mock = createMockBwg();
  (window as unknown as { bwg: BwgApi }).bwg = mock;
  return mock;
}

/** The id of the seeded trades site ("Acme Plumbing"). */
export function tradesSiteId(mock: MockBwg): string {
  const found = [...mock.__sites.values()].find((s) => s.businessType === 'trades');
  if (!found) throw new Error('No trades site seeded');
  return found.id;
}

/** The id of the seeded restaurant site ("Harbor Bistro"). */
export function restaurantSiteId(mock: MockBwg): string {
  const found = [...mock.__sites.values()].find((s) => s.businessType === 'restaurant');
  if (!found) throw new Error('No restaurant site seeded');
  return found.id;
}
