/**
 * IPC handlers for window.bwg.
 *
 * All arguments are zod-validated here in main (context-isolated preload only
 * forwards). Named failures are thrown as Error with a "CODE: message" prefix
 * so the renderer can branch on the code:
 * - INVALID_INPUT:<details>
 * - SITE_NOT_FOUND:<id>
 * - THEME_NOT_FOUND:<themeId>
 * - THEME_INCOMPATIBLE:<themeId>   (theme does not support the site's business type)
 * - EXPORT_DEST_NOT_EMPTY:<dir>
 * - EXPORT_DEST_NOT_DIR:<path>
 *
 * createHandlers() is pure and unit-testable; registerIpc() wires it to
 * Electron's ipcMain.
 */
import { ipcMain } from 'electron';
import { z } from 'zod';
import type {
  ExportResult,
  RenderedPage,
  Site,
  SiteSummary,
  ThemeInfo,
  ValidationIssue,
} from '../../shared/types.js';
import {
  businessProfilePatchSchema,
  exportRunSchema,
  newSiteInputSchema,
  setThemeSchema,
  siteIdSchema,
} from '../../shared/schemas.js';
import type { SiteStore } from './db.js';
import { getTheme, listThemes } from './themes/index.js';
import { BwgError, renderPreviewPages, runExport, validateSiteExport } from './exporter.js';

export type IpcHandler = (event: unknown, ...args: unknown[]) => Promise<unknown>;

export interface IpcDeps {
  store: SiteStore;
  /** Shows the native directory picker; resolves to the chosen path or null. */
  pickDirectory: () => Promise<string | null>;
}

function invalidInput(e: z.ZodError): Error {
  const details = e.issues.map((i) => `${i.path.join('.') || '(root)'}: ${i.message}`).join('; ');
  return new Error(`INVALID_INPUT: ${details}`);
}

function parse<T>(schema: z.ZodType<T>, value: unknown): T {
  const r = schema.safeParse(value);
  if (!r.success) throw invalidInput(r.error);
  return r.data;
}

function toIpcError(e: unknown): Error {
  if (e instanceof BwgError) return new Error(`${e.code}: ${e.message.slice(e.code.length + 2)}`);
  return e instanceof Error ? e : new Error(String(e));
}

async function guarded<T>(fn: () => T | Promise<T>): Promise<T> {
  try {
    return await fn();
  } catch (e) {
    throw toIpcError(e);
  }
}

export const CHANNELS = {
  sitesList: 'bwg:sites:list',
  sitesCreate: 'bwg:sites:create',
  sitesGet: 'bwg:sites:get',
  sitesUpdateProfile: 'bwg:sites:updateProfile',
  sitesDelete: 'bwg:sites:delete',
  sitesSetTheme: 'bwg:sites:setTheme',
  themesList: 'bwg:themes:list',
  previewRender: 'bwg:preview:render',
  exportValidate: 'bwg:export:validate',
  exportRun: 'bwg:export:run',
  dialogPickDirectory: 'bwg:dialog:pickDirectory',
} as const;

/** Pure handler table (no Electron imports at call time beyond registration). */
export function createHandlers(deps: IpcDeps): Record<string, IpcHandler> {
  const { store } = deps;

  const needSite = (id: string): Site => {
    const site = store.get(id);
    if (!site) throw new BwgError('SITE_NOT_FOUND', `No site with id "${id}".`);
    return site;
  };

  const checkTheme = (site: Site, themeId: string) => {
    const theme = getTheme(themeId);
    if (!theme) throw new BwgError('THEME_NOT_FOUND', `Unknown theme "${themeId}".`);
    if (!theme.info.businessTypes.includes(site.businessType)) {
      throw new BwgError(
        'THEME_INCOMPATIBLE',
        `Theme "${themeId}" does not support business type "${site.businessType}".`,
      );
    }
  };

  return {
    [CHANNELS.sitesList]: async (): Promise<SiteSummary[]> => guarded(() => store.list()),

    [CHANNELS.sitesCreate]: async (_e, input: unknown): Promise<Site> =>
      guarded(() => {
        const parsed = parse(newSiteInputSchema, input);
        const theme = getTheme(parsed.themeId);
        if (!theme) throw new BwgError('THEME_NOT_FOUND', `Unknown theme "${parsed.themeId}".`);
        if (!theme.info.businessTypes.includes(parsed.businessType)) {
          throw new BwgError(
            'THEME_INCOMPATIBLE',
            `Theme "${parsed.themeId}" does not support business type "${parsed.businessType}".`,
          );
        }
        return store.create(parsed);
      }),

    [CHANNELS.sitesGet]: async (_e, id: unknown): Promise<Site | null> =>
      guarded(() => store.get(parse(siteIdSchema, id))),

    [CHANNELS.sitesUpdateProfile]: async (_e, id: unknown, patch: unknown): Promise<Site> =>
      guarded(() => {
        const siteId = parse(siteIdSchema, id);
        needSite(siteId);
        return store.updateProfile(siteId, parse(businessProfilePatchSchema, patch));
      }),

    [CHANNELS.sitesDelete]: async (_e, id: unknown): Promise<boolean> =>
      guarded(() => store.delete(parse(siteIdSchema, id))),

    [CHANNELS.sitesSetTheme]: async (_e, id: unknown, themeId: unknown): Promise<Site> =>
      guarded(() => {
        const { id: siteId, themeId: tid } = parse(setThemeSchema, { id, themeId });
        const site = needSite(siteId);
        checkTheme(site, tid);
        return store.setTheme(siteId, tid);
      }),

    [CHANNELS.themesList]: async (): Promise<ThemeInfo[]> => guarded(() => listThemes()),

    [CHANNELS.previewRender]: async (_e, id: unknown): Promise<RenderedPage[]> =>
      guarded(() => renderPreviewPages(needSite(parse(siteIdSchema, id)))),

    [CHANNELS.exportValidate]: async (
      _e,
      id: unknown,
    ): Promise<{ ok: boolean; issues: ValidationIssue[] }> =>
      guarded(() => validateSiteExport(deps, parse(siteIdSchema, id))),

    [CHANNELS.exportRun]: async (_e, id: unknown, destDir: unknown): Promise<ExportResult> =>
      guarded(async () => {
        const { id: siteId, destDir: dir } = parse(exportRunSchema, { id, destDir });
        return runExport(deps, siteId, dir);
      }),

    [CHANNELS.dialogPickDirectory]: async (): Promise<string | null> =>
      guarded(() => deps.pickDirectory()),
  };
}

/** Wire the handler table to Electron's ipcMain. Call once from main.ts. */
export function registerIpc(deps: IpcDeps): void {
  for (const [channel, handler] of Object.entries(createHandlers(deps))) {
    ipcMain.handle(channel, handler as (...args: unknown[]) => Promise<unknown>);
  }
}
