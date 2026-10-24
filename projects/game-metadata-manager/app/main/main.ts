import { app, BrowserWindow, ipcMain } from 'electron';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { openDatabase } from '../db/schema.js';

// dist/main.js is bundled as ESM ("type": "module"), where __dirname does not
// exist. Resolve the bundle directory from import.meta instead.
const BUNDLE_DIR =
  typeof __dirname === 'string' ? __dirname : dirname(fileURLToPath(import.meta.url));
import { scanRoots } from '../engine/scanner.js';
import { Library } from '../engine/library.js';
import { ArtworkStore } from '../engine/artwork.js';
import { ChangeLog } from '../engine/changes.js';
import { BundleIO } from '../engine/bundle.js';
import { GMM_CHANNELS } from '../shared/ipc-contract.js';
import { schemas, type Channel } from './validators.js';

let win: BrowserWindow | null = null;

function createWindow(): void {
  win = new BrowserWindow({
    width: 1180,
    height: 780,
    backgroundColor: '#14161a',
    webPreferences: {
      preload: join(BUNDLE_DIR, 'preload.mjs'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  void win.loadFile(join(BUNDLE_DIR, 'index.html'));
  win.on('closed', () => {
    win = null;
  });
  // Headless smoke hook: when GMM_SMOKE=1, report once the real renderer
  // bundle loads and exit. Used by `npm run smoke` under xvfb on Linux.
  if (process.env['GMM_SMOKE'] === '1') {
    win.webContents.once('did-finish-load', () => {
      console.log('[smoke] SMOKE_OK: renderer bundle loaded in a real window');
      setTimeout(() => app.quit(), 500).unref();
    });
    setTimeout(() => {
      console.error('[smoke] SMOKE_FAIL: renderer did not load in time');
      app.exit(1);
    }, 20000).unref();
  }
}

type Context = {
  library: Library;
  artwork: ArtworkStore;
  changes: ChangeLog;
  bundles: BundleIO;
};

function buildContext(userData: string): Context {
  const db = openDatabase(join(userData, 'gmm.db'));
  const library = new Library(db);
  const artwork = new ArtworkStore(db, join(userData, 'artwork-cache'));
  const changes = new ChangeLog(db);
  const bundles = new BundleIO(library, artwork, changes);
  return { library, artwork, changes, bundles };
}

const HANDLERS: Record<Channel, (ctx: Context, args: unknown) => unknown> = {
  'lib:importRoots': (ctx, args) => {
    const { roots } = schemas['lib:importRoots'].parse(args);
    const discovered = scanRoots(roots);
    return ctx.library.importDiscovered(discovered);
  },
  'lib:list': (ctx, args) => {
    schemas['lib:list'].parse(args);
    return ctx.library.list();
  },
  'lib:rescan': (ctx, args) => {
    schemas['lib:rescan'].parse(args);
    return ctx.library.rescan();
  },
  'game:update': (ctx, args) => {
    const { gameId, patch } = schemas['game:update'].parse(args);
    if (patch.tagIds !== undefined) {
      const valid = new Set(ctx.library.listTags().map((t) => t.id));
      for (const id of patch.tagIds) {
        if (!valid.has(id)) throw new Error(`unknown tag id: ${id}`);
      }
    }
    if (patch.collectionIds !== undefined) {
      const valid = new Set(ctx.library.listCollections().map((c) => c.id));
      for (const id of patch.collectionIds) {
        if (!valid.has(id)) throw new Error(`unknown collection id: ${id}`);
      }
    }
    if (patch.artworkId !== undefined && patch.artworkId !== null) {
      if (!ctx.artwork.get(patch.artworkId)) throw new Error('unknown artwork id');
    }
    return ctx.library.update(gameId, patch);
  },
  'artwork:add': (ctx, args) => {
    const { sourcePath, provenance } = schemas['artwork:add'].parse(args);
    return ctx.artwork.add(sourcePath, provenance);
  },
  'artwork:list': (ctx, args) => {
    schemas['artwork:list'].parse(args);
    return ctx.artwork.list();
  },
  'artwork:fileUrl': (ctx, args) => {
    const { artworkId } = schemas['artwork:fileUrl'].parse(args);
    return ctx.artwork.fileUrl(artworkId);
  },
  'tags:list': (ctx, args) => {
    schemas['tags:list'].parse(args);
    return ctx.library.listTags();
  },
  'tags:add': (ctx, args) => {
    const { name } = schemas['tags:add'].parse(args);
    return ctx.library.addTag(name);
  },
  'tags:remove': (ctx, args) => {
    const { id } = schemas['tags:remove'].parse(args);
    ctx.library.removeTag(id);
    return undefined;
  },
  'collections:list': (ctx, args) => {
    schemas['collections:list'].parse(args);
    return ctx.library.listCollections();
  },
  'collections:add': (ctx, args) => {
    const { name } = schemas['collections:add'].parse(args);
    return ctx.library.addCollection(name);
  },
  'collections:remove': (ctx, args) => {
    const { id } = schemas['collections:remove'].parse(args);
    ctx.library.removeCollection(id);
    return undefined;
  },
  'bundle:export': (ctx, args) => {
    schemas['bundle:export'].parse(args);
    return { json: ctx.bundles.exportBundle() };
  },
  'bundle:import': (ctx, args) => {
    const { jsonText } = schemas['bundle:import'].parse(args);
    return ctx.bundles.importBundle(jsonText);
  },
  'changes:list': (ctx, args) => {
    const { gameId } = schemas['changes:list'].parse(args);
    return ctx.changes.listForGame(gameId);
  },
  'changes:undo': (ctx, args) => {
    schemas['changes:undo'].parse(args);
    return ctx.changes.undo((entry) => {
      if (entry.field === 'import') {
        // Undo of a bundle-added game removes the game entirely.
        ctx.library.removeGame(entry.gameId);
      } else {
        ctx.library.setField(entry.gameId, entry.field, entry.before);
      }
    });
  },
};

function registerHandlers(ctx: Context): void {
  for (const channel of GMM_CHANNELS) {
    ipcMain.handle(channel, async (_event, args: unknown) => {
      try {
        const handler = HANDLERS[channel as Channel];
        return await handler(ctx, args);
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        throw new Error(`${channel} failed: ${message}`);
      }
    });
  }
}

void app.whenReady().then(() => {
  const ctx = buildContext(app.getPath('userData'));
  registerHandlers(ctx);
  createWindow();
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
