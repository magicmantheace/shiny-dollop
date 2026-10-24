import { useEffect, useMemo, useState } from 'react';
import { useLibraryData } from './hooks';
import type { BundleImportResult } from './gmm';
import { LibraryView } from './components/LibraryView';
import { GameDetailView } from './components/GameDetailView';
import { ArtworkPanel } from './components/ArtworkPanel';
import { TagsCollectionsPanel } from './components/TagsCollectionsPanel';
import { BundlePanel } from './components/BundlePanel';
import { ImportPanel } from './components/ImportPanel';
import { UndoButton } from './components/UndoButton';
import './styles.css';

type View = 'library' | 'artwork' | 'tags' | 'bundles' | 'import';

const NAV: { id: View; label: string }[] = [
  { id: 'library', label: 'Library' },
  { id: 'artwork', label: 'Artwork' },
  { id: 'tags', label: 'Tags & Collections' },
  { id: 'bundles', label: 'Bundles' },
  { id: 'import', label: 'Import' },
];

export function App() {
  const [view, setView] = useState<View>('library');
  const [selectedGameId, setSelectedGameId] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const data = useLibraryData(refreshKey);
  const bump = () => setRefreshKey((k) => k + 1);

  // Lift the bundle import result above BundlePanel: a refresh unmounting the
  // panel must not discard the counts / conflict decisions the user needs to see.
  const [bundleImportResult, setBundleImportResult] = useState<BundleImportResult | null>(null);

  // Once the library has loaded once, keep the current view mounted during
  // refreshes instead of replacing it with the loading state (which unmounts
  // panels like BundlePanel and drops their local state).
  const [hasLoadedOnce, setHasLoadedOnce] = useState(false);
  useEffect(() => {
    if (!data.loading) setHasLoadedOnce(true);
  }, [data.loading]);
  const showContent = hasLoadedOnce ? !data.error : !data.loading && !data.error;

  const selectedGame = useMemo(
    () => data.games.find((g) => g.id === selectedGameId) ?? null,
    [data.games, selectedGameId],
  );

  const go = (next: View) => {
    setSelectedGameId(null);
    setView(next);
  };

  return (
    <div className="app">
      <header className="header">
        <div className="header-title">
          <h1>Game Library Metadata Enricher</h1>
        </div>
        <nav className="nav" aria-label="Main">
          {NAV.map((item) => (
            <button
              key={item.id}
              className={`nav-btn${view === item.id ? ' active' : ''}`}
              onClick={() => go(item.id)}
              aria-current={view === item.id ? 'page' : undefined}
            >
              {item.label}
            </button>
          ))}
        </nav>
        <UndoButton onUndone={bump} />
      </header>

      <main className="main">
        {data.loading && <p className="muted">Loading library…</p>}
        {data.error && (
          <p className="error" role="alert">
            Failed to load library: {data.error}
          </p>
        )}
        {showContent && (
          <>
            {view === 'library' &&
              (selectedGame ? (
                <GameDetailView
                  key={selectedGame.id}
                  game={selectedGame}
                  tags={data.tags}
                  collections={data.collections}
                  artworks={data.artworks}
                  onBack={() => setSelectedGameId(null)}
                  onChanged={bump}
                />
              ) : (
                <LibraryView
                  games={data.games}
                  tags={data.tags}
                  collections={data.collections}
                  onSelect={setSelectedGameId}
                  onChanged={bump}
                />
              ))}
            {view === 'artwork' && <ArtworkPanel artworks={data.artworks} onChanged={bump} />}
            {view === 'tags' && (
              <TagsCollectionsPanel
                tags={data.tags}
                collections={data.collections}
                onChanged={bump}
              />
            )}
            {view === 'bundles' && (
              <BundlePanel
                onChanged={bump}
                importResult={bundleImportResult}
                onImportResultChange={setBundleImportResult}
              />
            )}
            {view === 'import' && <ImportPanel onChanged={bump} />}
          </>
        )}
      </main>

      <footer className="footer">
        Metadata only — this app never launches, moves, or deletes games. Artwork is
        cached locally with its provenance.
      </footer>
    </div>
  );
}
