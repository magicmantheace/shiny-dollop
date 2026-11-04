/**
 * IPC handler tests: zod validation in main, named errors, and delegation.
 * Electron is mocked; the store is an in-memory stub.
 */
import { describe, expect, it, vi, beforeEach } from 'vitest';

vi.mock('electron', () => ({
  ipcMain: { handle: vi.fn() },
}));

import { createHandlers, CHANNELS, type IpcDeps } from '../../electron/main/ipc.js';
import type { Site, SiteSummary } from '../../shared/types.js';
import type { SiteStore } from '../../electron/main/db.js';
import { makeProfile } from './fixtures.js';

function stubStore(): SiteStore & { sites: Map<string, Site> } {
  const sites = new Map<string, Site>();
  const now = '2026-01-01T00:00:00.000Z';
  const store: SiteStore = {
    list: (): SiteSummary[] =>
      [...sites.values()].map(({ id, name, businessType, themeId, updatedAt }) => ({
        id, name, businessType, themeId, updatedAt,
      })),
    create: (input) => {
      const site: Site = {
        id: `id-${sites.size + 1}`,
        name: input.name,
        businessType: input.businessType,
        themeId: input.themeId,
        updatedAt: now,
        profile: {
          name: input.name, tagline: '', about: '',
          contact: { phone: '', email: '', address: '', website: '' },
          hours: { label: 'Hours', lines: [] },
          services: [], menuSections: [], social: [],
          seo: { title: input.name, description: '' },
        },
      };
      sites.set(site.id, site);
      return site;
    },
    get: (id) => sites.get(id) ?? null,
    updateProfile: (id, patch) => {
      const site = sites.get(id);
      if (!site) throw new Error(`SITE_NOT_FOUND: No site with id "${id}".`);
      const profile = { ...site.profile, ...patch };
      const updated = { ...site, profile, name: profile.name, updatedAt: now };
      sites.set(id, updated);
      return updated;
    },
    delete: (id) => sites.delete(id),
    setTheme: (id, themeId) => {
      const site = sites.get(id);
      if (!site) throw new Error(`SITE_NOT_FOUND: No site with id "${id}".`);
      const updated = { ...site, themeId };
      sites.set(id, updated);
      return updated;
    },
    schemaVersion: () => 1,
    close: () => {},
  };
  return Object.assign(store, { sites });
}

let deps: IpcDeps;
let handlers: ReturnType<typeof createHandlers>;

beforeEach(() => {
  deps = { store: stubStore(), pickDirectory: async () => '/tmp/picked' };
  handlers = createHandlers(deps);
});

const call = (channel: string, ...args: unknown[]) => handlers[channel]!(undefined, ...args);

describe('sites', () => {
  it('creates a site with valid input', async () => {
    const site = (await call(CHANNELS.sitesCreate, {
      name: 'Acme', businessType: 'trades', themeId: 'trades',
    })) as Site;
    expect(site.name).toBe('Acme');
    expect(site.businessType).toBe('trades');
  });

  it('rejects invalid input with INVALID_INPUT', async () => {
    await expect(call(CHANNELS.sitesCreate, { name: '', businessType: 'trades', themeId: 'trades' })).rejects.toThrow(
      /INVALID_INPUT/,
    );
    await expect(
      call(CHANNELS.sitesCreate, { name: 'x', businessType: 'nope', themeId: 'trades' }),
    ).rejects.toThrow(/INVALID_INPUT/);
  });

  it('rejects unknown and incompatible themes with named errors', async () => {
    await expect(
      call(CHANNELS.sitesCreate, { name: 'x', businessType: 'trades', themeId: 'nope' }),
    ).rejects.toThrow(/THEME_NOT_FOUND/);
    await expect(
      call(CHANNELS.sitesCreate, { name: 'x', businessType: 'trades', themeId: 'restaurant' }),
    ).rejects.toThrow(/THEME_INCOMPATIBLE/);
  });

  it('gets, lists, updates, sets theme and deletes', async () => {
    const created = (await call(CHANNELS.sitesCreate, {
      name: 'Acme', businessType: 'author', themeId: 'author',
    })) as Site;
    expect(await call(CHANNELS.sitesGet, created.id)).toEqual(created);
    expect(await call(CHANNELS.sitesGet, 'missing')).toBeNull();
    expect(((await call(CHANNELS.sitesList)) as SiteSummary[])).toHaveLength(1);

    const updated = (await call(CHANNELS.sitesUpdateProfile, created.id, {
      contact: { phone: '555-1' },
    })) as Site;
    expect(updated.profile.contact.phone).toBe('555-1');

    await expect(call(CHANNELS.sitesUpdateProfile, 'missing', {})).rejects.toThrow(/SITE_NOT_FOUND/);
    await expect(call(CHANNELS.sitesSetTheme, created.id, 'trades')).rejects.toThrow(/THEME_INCOMPATIBLE/);
    const themed = (await call(CHANNELS.sitesSetTheme, created.id, 'author')) as Site;
    expect(themed.themeId).toBe('author');

    expect(await call(CHANNELS.sitesDelete, created.id)).toBe(true);
    expect(await call(CHANNELS.sitesDelete, created.id)).toBe(false);
  });

  it('rejects malformed ids and patches', async () => {
    await expect(call(CHANNELS.sitesGet, '')).rejects.toThrow(/INVALID_INPUT/);
    const created = (await call(CHANNELS.sitesCreate, {
      name: 'Acme', businessType: 'trades', themeId: 'trades',
    })) as Site;
    await expect(call(CHANNELS.sitesUpdateProfile, created.id, { services: 'not-an-array' })).rejects.toThrow(
      /INVALID_INPUT/,
    );
  });
});

describe('themes', () => {
  it('lists the four themes', async () => {
    const themes = (await call(CHANNELS.themesList)) as { id: string }[];
    expect(themes.map((t) => t.id).sort()).toEqual(['author', 'localbiz', 'restaurant', 'trades']);
  });
});

describe('preview', () => {
  it('renders HTML pages for a site', async () => {
    const created = (await call(CHANNELS.sitesCreate, {
      name: 'Acme', businessType: 'trades', themeId: 'trades',
    })) as Site;
    await call(CHANNELS.sitesUpdateProfile, created.id, makeProfile());
    const pages = (await call(CHANNELS.previewRender, created.id)) as { path: string; html: string }[];
    expect(pages.map((p) => p.path)).toEqual(['index.html', 'services.html', 'contact.html']);
    for (const page of pages) expect(page.html).toContain('<!DOCTYPE html>');
    await expect(call(CHANNELS.previewRender, 'missing')).rejects.toThrow(/SITE_NOT_FOUND/);
  });
});

describe('export', () => {
  it('validate reports blocking issues for an empty profile', async () => {
    const created = (await call(CHANNELS.sitesCreate, {
      name: 'Acme', businessType: 'trades', themeId: 'trades',
    })) as Site;
    const result = (await call(CHANNELS.exportValidate, created.id)) as { ok: boolean; issues: unknown[] };
    expect(result.ok).toBe(false);
    expect(result.issues.length).toBeGreaterThan(0);
  });

  it('dialog.pickDirectory delegates to the injected picker', async () => {
    expect(await call(CHANNELS.dialogPickDirectory)).toBe('/tmp/picked');
  });
});

describe('channels', () => {
  it('exposes the exact bwg channel set', () => {
    expect(Object.values(CHANNELS).sort()).toEqual(
      [
        'bwg:sites:list',
        'bwg:sites:create',
        'bwg:sites:get',
        'bwg:sites:updateProfile',
        'bwg:sites:delete',
        'bwg:sites:setTheme',
        'bwg:themes:list',
        'bwg:preview:render',
        'bwg:export:validate',
        'bwg:export:run',
        'bwg:dialog:pickDirectory',
      ].sort(),
    );
  });
});
