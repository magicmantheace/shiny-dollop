/**
 * Global renderer store: games, schedules, toasts, and live backup events.
 * All backend access goes through window.saveManager (typed in shared/types).
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import type {
  Backup,
  BackupCompletedEvent,
  BackupFailedEvent,
  BackupProgressEvent,
  Game,
  Schedule,
} from '../shared/types';
import { IpcError, unwrap } from './api';
import { errorSummary } from './errorMessages';

export interface Toast {
  id: number;
  kind: 'success' | 'error' | 'info';
  title: string;
  message: string;
}

export interface GameStats {
  backupCount: number;
  lastBackupAt: string | null;
}

interface SaveManagerStore {
  games: Game[];
  gamesLoading: boolean;
  gamesError: string | null;
  gameStats: Record<number, GameStats>;
  refreshGames: () => Promise<void>;
  addGame: (name: string, savePath: string, source?: Game['source']) => Promise<Game>;
  updateGame: (id: number, patch: { name?: string; savePath?: string }) => Promise<Game>;
  removeGame: (id: number) => Promise<void>;
  schedules: Schedule[];
  schedulesLoading: boolean;
  schedulesError: string | null;
  refreshSchedules: () => Promise<void>;
  setSchedule: (gameId: number, intervalMinutes: number, enabled: boolean) => Promise<void>;
  deleteSchedule: (gameId: number) => Promise<void>;
  toasts: Toast[];
  pushToast: (kind: Toast['kind'], title: string, message: string) => void;
  dismissToast: (id: number) => void;
  /** Active backup progress keyed by gameId. */
  progress: Record<number, BackupProgressEvent>;
  /** Bumped whenever a backup completes/fails so detail views refresh. */
  backupRevision: number;
}

const StoreContext = createContext<SaveManagerStore | null>(null);

let toastSeq = 1;

export function SaveManagerProvider({ children }: { children: ReactNode }): ReactNode {
  const [games, setGames] = useState<Game[]>([]);
  const [gamesLoading, setGamesLoading] = useState(true);
  const [gamesError, setGamesError] = useState<string | null>(null);
  const [gameStats, setGameStats] = useState<Record<number, GameStats>>({});
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [schedulesLoading, setSchedulesLoading] = useState(true);
  const [schedulesError, setSchedulesError] = useState<string | null>(null);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [progress, setProgress] = useState<Record<number, BackupProgressEvent>>({});
  const [backupRevision, setBackupRevision] = useState(0);
  const gamesRef = useRef<Game[]>([]);
  gamesRef.current = games;

  const pushToast = useCallback((kind: Toast['kind'], title: string, message: string) => {
    const id = toastSeq++;
    setToasts((prev) => [...prev.slice(-4), { id, kind, title, message }]);
    window.setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 9000);
  }, []);

  const dismissToast = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const loadGameStats = useCallback(async (list: Game[]) => {
    const entries = await Promise.all(
      list.map(async (g) => {
        try {
          const backups: Backup[] = unwrap(await window.saveManager.backups.list({ gameId: g.id }));
          return [
            g.id,
            {
              backupCount: backups.length,
              lastBackupAt: backups.length > 0 ? (backups[0]?.createdAt ?? null) : null,
            },
          ] as const;
        } catch {
          return [g.id, { backupCount: 0, lastBackupAt: null }] as const;
        }
      }),
    );
    setGameStats(Object.fromEntries(entries));
  }, []);

  const refreshGames = useCallback(async () => {
    setGamesLoading(true);
    setGamesError(null);
    try {
      const list = unwrap(await window.saveManager.games.list());
      setGames(list);
      await loadGameStats(list);
    } catch (err) {
      const message =
        err instanceof IpcError ? errorSummary(err.code, err.message) : 'Could not load the game library.';
      setGamesError(message);
    } finally {
      setGamesLoading(false);
    }
  }, [loadGameStats]);

  const refreshSchedules = useCallback(async () => {
    setSchedulesLoading(true);
    setSchedulesError(null);
    try {
      setSchedules(unwrap(await window.saveManager.schedules.list()));
    } catch (err) {
      const message =
        err instanceof IpcError ? errorSummary(err.code, err.message) : 'Could not load schedules.';
      setSchedulesError(message);
    } finally {
      setSchedulesLoading(false);
    }
  }, []);

  const addGame = useCallback(
    async (name: string, savePath: string, source?: Game['source']): Promise<Game> => {
      const input =
        source === undefined ? { name, savePath } : { name, savePath, source };
      const game = unwrap(await window.saveManager.games.add(input));
      await refreshGames();
      pushToast('success', 'Game added', `"${game.name}" is now tracked.`);
      return game;
    },
    [pushToast, refreshGames],
  );

  const updateGame = useCallback(
    async (id: number, patch: { name?: string; savePath?: string }): Promise<Game> => {
      const game = unwrap(await window.saveManager.games.update({ id, ...patch }));
      await refreshGames();
      return game;
    },
    [refreshGames],
  );

  const removeGame = useCallback(
    async (id: number): Promise<void> => {
      unwrap(await window.saveManager.games.remove({ id }));
      await refreshGames();
    },
    [pushToast, refreshGames],
  );

  const setSchedule = useCallback(
    async (gameId: number, intervalMinutes: number, enabled: boolean): Promise<void> => {
      unwrap(await window.saveManager.schedules.set({ gameId, intervalMinutes, enabled }));
      await refreshSchedules();
    },
    [refreshSchedules],
  );

  const deleteSchedule = useCallback(
    async (gameId: number): Promise<void> => {
      unwrap(await window.saveManager.schedules.delete({ gameId }));
      await refreshSchedules();
    },
    [refreshSchedules],
  );

  // Subscribe to live backup events once.
  useEffect(() => {
    const offProgress = window.saveManager.events.onBackupProgress((e: BackupProgressEvent) => {
      setProgress((prev) => ({ ...prev, [e.gameId]: e }));
    });
    const offCompleted = window.saveManager.events.onBackupCompleted((e: BackupCompletedEvent) => {
      setProgress((prev) => {
        const next = { ...prev };
        delete next[e.gameId];
        return next;
      });
      setBackupRevision((r) => r + 1);
      const game = gamesRef.current.find((g) => g.id === e.gameId);
      const name = game ? `"${game.name}"` : `Game #${e.gameId}`;
      const skippedFiles = e.skippedFiles ?? [];
      if (skippedFiles.length > 0) {
        // A "successful" backup that excluded saves must never look like an
        // ordinary success: name the skipped paths and reasons.
        const list = skippedFiles.map((s) => `${s.relPath} (${s.reason})`).join('; ');
        pushToast(
          'error',
          'Backup finished — files were skipped',
          `${name}: ${skippedFiles.length} file${skippedFiles.length === 1 ? '' : 's'} NOT backed up: ${list}`,
        );
      } else if (e.skipped) {
        pushToast('info', 'Backup skipped', `${name}: no changes since the last backup.`);
      } else {
        pushToast(
          'success',
          'Backup complete',
          `${name}: ${e.fileCount} file${e.fileCount === 1 ? '' : 's'} saved${e.label ? ` as "${e.label}"` : ''}.`,
        );
      }
      void refreshGames();
    });
    const offFailed = window.saveManager.events.onBackupFailed((e: BackupFailedEvent) => {
      setProgress((prev) => {
        const next = { ...prev };
        delete next[e.gameId];
        return next;
      });
      setBackupRevision((r) => r + 1);
      const game = gamesRef.current.find((g) => g.id === e.gameId);
      const name = game ? `"${game.name}"` : `Game #${e.gameId}`;
      pushToast('error', `Backup failed for ${name}`, errorSummary(e.code, e.message));
    });
    return () => {
      offProgress();
      offCompleted();
      offFailed();
    };
  }, [pushToast, refreshGames]);

  useEffect(() => {
    void refreshGames();
    void refreshSchedules();
  }, [refreshGames, refreshSchedules]);

  const value = useMemo<SaveManagerStore>(
    () => ({
      games,
      gamesLoading,
      gamesError,
      gameStats,
      refreshGames,
      addGame,
      updateGame,
      removeGame,
      schedules,
      schedulesLoading,
      schedulesError,
      refreshSchedules,
      setSchedule,
      deleteSchedule,
      toasts,
      pushToast,
      dismissToast,
      progress,
      backupRevision,
    }),
    [
      games,
      gamesLoading,
      gamesError,
      gameStats,
      refreshGames,
      addGame,
      updateGame,
      removeGame,
      schedules,
      schedulesLoading,
      schedulesError,
      refreshSchedules,
      setSchedule,
      deleteSchedule,
      toasts,
      pushToast,
      dismissToast,
      progress,
      backupRevision,
    ],
  );

  return <StoreContext.Provider value={value}>{children}</StoreContext.Provider>;
}

export function useStore(): SaveManagerStore {
  const ctx = useContext(StoreContext);
  if (!ctx) {
    throw new Error('useStore must be used inside SaveManagerProvider');
  }
  return ctx;
}
