/**
 * Canonical contract for the Small Business Website Generator.
 *
 * Worker A (backend) and Worker B (renderer) both build against this exact
 * shape. Do not change these types without coordinating both sides.
 */

export type BusinessType = 'trades' | 'author' | 'restaurant' | 'localbiz';

export interface ServiceItem {
  title: string;
  description: string;
}

export interface MenuItem {
  name: string;
  description: string;
  price: string;
}

export interface MenuSection {
  name: string;
  items: MenuItem[];
}

export interface BusinessProfile {
  name: string;
  tagline: string;
  about: string;
  contact: { phone: string; email: string; address: string; website: string };
  hours: { label: string; lines: string[] };
  services: ServiceItem[];
  menuSections: MenuSection[]; // restaurant only; empty otherwise
  social: { label: string; url: string }[];
  seo: { title: string; description: string };
}

export interface SiteSummary {
  id: string;
  name: string;
  businessType: BusinessType;
  themeId: string;
  updatedAt: string;
}

export interface Site extends SiteSummary {
  profile: BusinessProfile;
}

export interface NewSiteInput {
  name: string;
  businessType: BusinessType;
  themeId: string;
}

export interface ThemeInfo {
  id: string;
  name: string;
  description: string;
  businessTypes: BusinessType[];
  pages: string[];
}

export interface RenderedPage {
  path: string;
  html: string;
}

export interface ValidationIssue {
  code: string;
  message: string;
  field?: string;
}

export interface ExportResult {
  ok: boolean;
  destDir: string;
  files: string[];
  issues: ValidationIssue[];
}

/**
 * Patch for sites.updateProfile: top-level scalars replace, the contact /
 * hours / seo objects merge key-by-key, and arrays (services, menuSections,
 * social, hours.lines) replace wholesale when present.
 */
export interface BusinessProfilePatch {
  name?: string;
  tagline?: string;
  about?: string;
  contact?: { phone?: string; email?: string; address?: string; website?: string };
  hours?: { label?: string; lines?: string[] };
  services?: ServiceItem[];
  menuSections?: MenuSection[];
  social?: { label: string; url: string }[];
  seo?: { title?: string; description?: string };
}

/**
 * Shape of `window.bwg` exposed by the preload script.
 *
 * - sites.list() -> SiteSummary[]
 * - sites.create(input) -> Site
 * - sites.get(id) -> Site | null
 * - sites.updateProfile(id, patch) -> Site
 * - sites.delete(id) -> boolean
 * - sites.setTheme(id, themeId) -> Site
 * - themes.list() -> ThemeInfo[]
 * - preview.render(id) -> RenderedPage[]
 * - export.validate(id) -> { ok: boolean; issues: ValidationIssue[] }
 * - export.run(id, destDir) -> ExportResult
 * - dialog.pickDirectory() -> string | null
 */
export interface BwgApi {
  sites: {
    list(): Promise<SiteSummary[]>;
    create(input: NewSiteInput): Promise<Site>;
    updateProfile(id: string, patch: BusinessProfilePatch): Promise<Site>;
    delete(id: string): Promise<boolean>;
    setTheme(id: string, themeId: string): Promise<Site>;
    get(id: string): Promise<Site | null>;
  };
  themes: {
    list(): Promise<ThemeInfo[]>;
  };
  preview: {
    render(id: string): Promise<RenderedPage[]>;
  };
  export: {
    validate(id: string): Promise<{ ok: boolean; issues: ValidationIssue[] }>;
    run(id: string, destDir: string): Promise<ExportResult>;
  };
  dialog: {
    pickDirectory(): Promise<string | null>;
  };
}
