/** Shared domain types. Imported by main, preload and renderer. No Node/Electron APIs here. */

export type GameSource = 'manual' | 'steam' | 'epic' | 'battlenet';

export type SortKey = 'title' | 'added' | 'lastPlayed' | 'playtime';

/** How a library entry can be started. */
export type LaunchCapability = 'direct' | 'native-uri' | 'open-client' | 'unavailable';

export interface Game {
  id: string;
  source: GameSource;
  externalId: string | null;
  title: string;
  /** Absolute executable path for manual games. Null for store entries without a local exe. */
  exePath: string | null;
  /** Normalized absolute path used for duplicate detection. Null when not applicable. */
  canonicalPath: string | null;
  /** Absolute install directory for store games (e.g. .../steamapps/common/<dir>). */
  installDir: string | null;
  /** Validated launch URI for store games (e.g. steam://rungameid/730). */
  launchUri: string | null;
  launchCapability: LaunchCapability;
  /** Human-readable reason for the capability (especially when unavailable). */
  launchReason: string | null;
  workingDir: string | null;
  args: string[];
  favorite: boolean;
  hidden: boolean;
  /** Stored cover-art filename (validated, app-data covers dir). Null when none. */
  coverPath: string | null;
  /** True when the stored executable/install dir is currently missing from disk. */
  missing: boolean;
  addedAt: string; // ISO UTC
  updatedAt: string; // ISO UTC
  lastPlayedAt: string | null; // ISO UTC
  totalPlayMs: number;
}

export type SessionState = 'running' | 'completed' | 'interrupted';
export type TrackingMethod = 'observed' | 'manual' | 'unavailable';

export interface Session {
  id: string;
  gameId: string;
  gameTitle: string;
  startedAt: string; // ISO UTC
  endedAt: string | null; // ISO UTC
  durationMs: number | null;
  state: SessionState;
  trackingMethod: TrackingMethod;
  notes: string | null;
}

export interface Settings {
  trackingEnabled: boolean;
  minimizeOnLaunch: boolean;
  theme: 'dark' | 'light' | 'system';
}

export interface SourceStatus {
  source: GameSource;
  available: boolean;
  /** Human-readable reason when unavailable or limited. */
  reason: string;
  lastScanAt: string | null;
  gamesFound: number;
}

export interface ApiError {
  code: string;
  message: string;
}

/** Every IPC call resolves to this shape. Main never throws across the boundary. */
export type ApiResult<T> = { ok: true; data: T } | { ok: false; error: ApiError };

/** Narrow typed API exposed to the renderer via the preload script. */
export interface GameLauncherApi {
  library: {
    list(query?: {
      search?: string;
      source?: GameSource;
      favoritesOnly?: boolean;
      sort?: SortKey;
    }): Promise<ApiResult<Game[]>>;
    addManual(input: {
      path: string;
      workingDir?: string;
      args?: string[];
    }): Promise<ApiResult<Game>>;
    update(input: {
      id: string;
      title?: string;
      workingDir?: string | null;
      args?: string[];
      hidden?: boolean;
      coverPath?: string | null;
    }): Promise<ApiResult<Game>>;
    remove(input: { id: string }): Promise<ApiResult<null>>;
    setFavorite(input: { id: string; favorite: boolean }): Promise<ApiResult<Game>>;
  };
  games: {
    launch(input: { id: string }): Promise<
      ApiResult<{ sessionId: string | null; alreadyRunning: boolean }>
    >;
  };
  sessions: {
    list(input?: { gameId?: string; limit?: number }): Promise<ApiResult<Session[]>>;
    clear(): Promise<ApiResult<null>>;
  };
  settings: {
    get(): Promise<ApiResult<Settings>>;
    update(input: Partial<Settings>): Promise<ApiResult<Settings>>;
  };
  files: {
    chooseExecutable(): Promise<ApiResult<{ path: string } | { canceled: true }>>;
    chooseCover(): Promise<ApiResult<{ coverPath: string } | { canceled: true }>>;
    coverData(input: { id: string }): Promise<ApiResult<{ dataUrl: string | null }>>;
  };
  sources: {
    status(): Promise<ApiResult<SourceStatus[]>>;
    scan(input: { source: GameSource }): Promise<ApiResult<{ scannedAt: string; gamesFound: number }>>;
    cancelScan(): Promise<ApiResult<{ cancelled: boolean }>>;
    openClient(input: { source: 'epic' | 'battlenet' }): Promise<ApiResult<{ opened: boolean }>>;
  };
}

declare global {
  interface Window {
    gameLauncher: GameLauncherApi;
  }
}
