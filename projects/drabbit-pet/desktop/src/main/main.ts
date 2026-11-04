/**
 * Drabbit Pet — Electron main process.
 *
 * Owns the ONE pet state (via PetService), the save file in userData,
 * the pet window (transparent, always-on-top, roaming the screen
 * bottom), the care-panel window, and the tray icon.
 *
 * This shell is the only place clocks live: it feeds `Date.now()` into
 * the clock-free core (project invariant).
 */
import { app, BrowserWindow, Menu, Tray, nativeImage, screen } from 'electron';
import fs from 'node:fs';
import path from 'node:path';
import { PetChannels } from '../shared/ipc-channels.js';
import type { ChangedEvent, RoamState } from '../shared/api-types.js';
import { PetService, systemClock } from './pet-service.js';
import { SaveStore } from './save-store.js';
import { TickService } from './tick-service.js';
import { RoamPlanner, type RoamBounds } from './roaming.js';
import { registerPetIpc } from './ipc.js';
import { registerCompanionIpc } from './companion-ipc.js';
import { CompanionConfigStore } from './server/companion-config.js';
import { CompanionService } from './server/companion-service.js';

const isDev = !!process.env.DRABBIT_DEV_SERVER;
const isSmoke = !!process.env.DRABBIT_SMOKE;

if (process.env.DRABBIT_USER_DATA) {
  app.setPath('userData', process.env.DRABBIT_USER_DATA);
}

const PET_SIZE = 220;
const PANEL_WIDTH = 430;
const PANEL_HEIGHT = 660;
const ROAM_INTERVAL_MS = 200;

let petWindow: BrowserWindow | null = null;
let panelWindow: BrowserWindow | null = null;
let tray: Tray | null = null;
let service: PetService | null = null;
let companion: CompanionService | null = null;
let tickService: TickService | null = null;
let roamTimer: ReturnType<typeof setInterval> | null = null;
let roamingPaused = false;
let isQuitting = false;
let lastHopping = false;
const planner = new RoamPlanner();

function log(msg: string): void {
  console.log(msg);
}

function rendererTarget(file: 'pet.html' | 'panel.html'): { kind: 'file'; path: string } | { kind: 'url'; url: string } {
  if (isDev && process.env.DRABBIT_DEV_SERVER) {
    return { kind: 'url', url: `${process.env.DRABBIT_DEV_SERVER}/${file}` };
  }
  return { kind: 'file', path: path.join(__dirname, '..', 'renderer', file) };
}

function loadRenderer(win: BrowserWindow, file: 'pet.html' | 'panel.html'): void {
  const target = rendererTarget(file);
  if (target.kind === 'file') {
    void win.loadFile(target.path);
  } else {
    void win.loadURL(target.url);
  }
}

/** The app window may never navigate away from its own content. */
function installSecurityGuards(win: BrowserWindow): void {
  win.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));
  win.webContents.on('will-navigate', (event, url) => {
    const target = rendererTarget('pet.html');
    const allowed = target.kind === 'url' ? url.startsWith(target.url.replace(/\/[^/]*$/, '')) : url.startsWith('file:');
    if (!allowed) event.preventDefault();
  });
}

function broadcast(channel: string, payload: unknown): void {
  for (const win of [petWindow, panelWindow]) {
    if (win && !win.isDestroyed()) {
      win.webContents.send(channel, payload);
    }
  }
}

function onPetChanged(summary: ChangedEvent['summary'], events: ChangedEvent['events']): void {
  broadcast(PetChannels.changed, { summary, events } satisfies ChangedEvent);
}

function workAreaBounds(): { bounds: RoamBounds; y: number } {
  const wa = screen.getPrimaryDisplay().workArea;
  return {
    bounds: { minX: wa.x, maxX: wa.x + wa.width - PET_SIZE },
    y: wa.y + wa.height - PET_SIZE,
  };
}

function createPetWindow(): void {
  const { bounds, y } = workAreaBounds();
  petWindow = new BrowserWindow({
    width: PET_SIZE,
    height: PET_SIZE,
    x: bounds.maxX, // starts bottom-right of the work area
    y,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    resizable: false,
    movable: false,
    skipTaskbar: true,
    hasShadow: false,
    title: 'Drabbit',
    webPreferences: {
      preload: path.join(__dirname, '..', 'preload', 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      webSecurity: true,
      allowRunningInsecureContent: false,
    },
  });
  petWindow.setAlwaysOnTop(true, 'floating');
  installSecurityGuards(petWindow);
  loadRenderer(petWindow, 'pet.html');
  // A desktop pet shouldn't be closed out from under its owner —
  // quitting happens from the tray.
  petWindow.on('close', (event) => {
    if (!isQuitting) event.preventDefault();
  });
  petWindow.on('closed', () => {
    petWindow = null;
  });
}

function createPanelWindow(): void {
  panelWindow = new BrowserWindow({
    width: PANEL_WIDTH,
    height: PANEL_HEIGHT,
    minWidth: 380,
    minHeight: 520,
    show: false,
    title: 'Drabbit — Care Panel',
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, '..', 'preload', 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      webSecurity: true,
      allowRunningInsecureContent: false,
    },
  });
  installSecurityGuards(panelWindow);
  loadRenderer(panelWindow, 'panel.html');
  // Hide instead of destroy so toggling is instant.
  panelWindow.on('close', (event) => {
    if (!isQuitting) {
      event.preventDefault();
      panelWindow?.hide();
    }
  });
  panelWindow.on('closed', () => {
    panelWindow = null;
  });
}

function togglePanel(): void {
  if (!panelWindow) createPanelWindow();
  if (!panelWindow) return;
  if (panelWindow.isVisible()) {
    panelWindow.hide();
  } else {
    service?.tick(); // show the freshest state
    panelWindow.show();
    panelWindow.focus();
  }
}

function trayIcon(): Electron.NativeImage {
  const iconPath = path.join(__dirname, '..', '..', 'assets', 'icon.png');
  if (fs.existsSync(iconPath)) {
    return nativeImage.createFromPath(iconPath).resize({ width: 24, height: 24 });
  }
  return nativeImage.createEmpty();
}

function createTray(): void {
  tray = new Tray(trayIcon());
  tray.setToolTip('Drabbit Pet');
  const menu = Menu.buildFromTemplate([
    {
      label: 'Show pet',
      click: () => {
        petWindow?.show();
        petWindow?.focus();
      },
    },
    { label: 'Care panel', click: () => togglePanel() },
    {
      label: 'Pause roaming',
      type: 'checkbox',
      checked: roamingPaused,
      click: (item) => {
        roamingPaused = item.checked;
      },
    },
    { type: 'separator' },
    {
      label: 'Quit',
      click: () => {
        isQuitting = true;
        app.quit();
      },
    },
  ]);
  tray.setContextMenu(menu);
  tray.on('click', () => togglePanel());
}

function startRoaming(): void {
  roamTimer = setInterval(() => {
    if (!petWindow || petWindow.isDestroyed() || !service) return;
    const { bounds, y } = workAreaBounds();
    const summary = service.getSummary();
    const [currentX] = petWindow.getPosition();
    const plan = planner.step(currentX ?? bounds.minX, bounds, {
      stage: summary.stage,
      asleep: summary.asleep,
      panelOpen: !!panelWindow?.isVisible(),
      paused: roamingPaused,
    });
    if (plan.x !== currentX) {
      petWindow.setPosition(plan.x, y);
    }
    if (plan.hopping !== lastHopping) {
      lastHopping = plan.hopping;
      broadcast(PetChannels.roamState, { hopping: plan.hopping } satisfies RoamState);
    }
  }, ROAM_INTERVAL_MS);
}

function startApp(): void {
  const store = new SaveStore(app.getPath('userData'), log);
  service = new PetService({ store, clock: systemClock, onChanged: onPetChanged, log });
  log(`[drabbit] pet loaded (${service.loadOutcome}): ${service.getSummary().name}`);
  service.tick(); // offline catch-up on launch

  registerPetIpc({
    service,
    openPanel: () => togglePanel(),
  });

  // Companion server (P3): a second front door to the same pet. It
  // runs only if the persisted switch in companion.json is on —
  // default off, so a fresh install (and the smoke profile) never
  // opens a port.
  companion = new CompanionService({
    store: new CompanionConfigStore(app.getPath('userData'), { log }),
    service,
    clock: systemClock,
    log,
  });
  registerCompanionIpc({ companion });
  void companion.init();

  createPetWindow();
  createPanelWindow();
  createTray();

  tickService = new TickService(service);
  tickService.start();
  startRoaming();

  if (isSmoke) {
    // Real windows opened with the production bundle: smoke passes.
    let loaded = 0;
    const onLoad = () => {
      loaded += 1;
      if (loaded >= 2) {
        console.log('SMOKE_OK');
        setTimeout(() => {
          isQuitting = true;
          app.quit();
        }, 300);
      }
    };
    petWindow?.webContents.once('did-finish-load', onLoad);
    panelWindow?.webContents.once('did-finish-load', onLoad);
  }
}

const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
} else {
  app.on('second-instance', () => {
    petWindow?.show();
    petWindow?.focus();
  });

  void app.whenReady().then(startApp);

  // Tray app: closing all windows does not quit.
  app.on('window-all-closed', () => undefined);

  app.on('before-quit', () => {
    isQuitting = true;
    tickService?.stop();
    if (roamTimer) clearInterval(roamTimer);
    void companion?.shutdown();
    service?.shutdown();
  });
}
