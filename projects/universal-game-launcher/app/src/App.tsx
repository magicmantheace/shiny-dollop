import { useCallback, useEffect, useState } from 'react';
import type { Game, Settings } from '../shared/types';
import { ApiCallError, getApi, unwrap } from './api';
import LibraryPage from './pages/LibraryPage';
import FavoritesPage from './pages/FavoritesPage';
import RecentPage from './pages/RecentPage';
import SettingsPage from './pages/SettingsPage';
import AddGameDialog from './components/AddGameDialog';

export type View = 'library' | 'favorites' | 'recent' | 'settings';

export default function App() {
  const [view, setView] = useState<View>('library');
  const [games, setGames] = useState<Game[]>([]);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [loading, setLoading] = useState(true);
  const [fatal, setFatal] = useState<string | null>(null);
  const [showAdd, setShowAdd] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const api = getApi();
      const [g, s] = await Promise.all([unwrap(api.library.list({})), unwrap(api.settings.get())]);
      setGames(g);
      setSettings(s);
      applyTheme(s.theme);
    } catch (err) {
      setFatal(err instanceof ApiCallError ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  if (fatal) {
    return (
      <div className="fatal">
        <h1>Couldn't start the launcher</h1>
        <p>{fatal}</p>
      </div>
    );
  }

  return (
    <div className="app">
      <nav className="sidebar" aria-label="Main navigation">
        <div className="brand">Universal Game Launcher</div>
        {(
          [
            ['library', 'Library'],
            ['favorites', 'Favorites'],
            ['recent', 'Recently Played'],
            ['settings', 'Settings'],
          ] as [View, string][]
        ).map(([v, label]) => (
          <button
            key={v}
            className={view === v ? 'nav-btn active' : 'nav-btn'}
            onClick={() => setView(v)}
            aria-current={view === v ? 'page' : undefined}
          >
            {label}
          </button>
        ))}
        <div className="sidebar-spacer" />
        <button className="btn primary" onClick={() => setShowAdd(true)}>
          + Add Game
        </button>
      </nav>
      <main className="content">
        {loading || !settings ? (
          <p className="muted">Loading library…</p>
        ) : view === 'library' ? (
          <LibraryPage games={games} onRefresh={refresh} onAdd={() => setShowAdd(true)} />
        ) : view === 'favorites' ? (
          <FavoritesPage games={games} onRefresh={refresh} onAdd={() => setShowAdd(true)} />
        ) : view === 'recent' ? (
          <RecentPage />
        ) : (
          <SettingsPage settings={settings} onRefresh={refresh} />
        )}
      </main>
      {showAdd && (
        <AddGameDialog
          onClose={() => setShowAdd(false)}
          onAdded={() => {
            setShowAdd(false);
            void refresh();
          }}
        />
      )}
    </div>
  );
}

function applyTheme(theme: Settings['theme']): void {
  const dark =
    theme === 'dark' ||
    (theme === 'system' &&
      typeof window.matchMedia === 'function' &&
      window.matchMedia('(prefers-color-scheme: dark)').matches);
  document.documentElement.dataset.theme = dark ? 'dark' : 'light';
}
