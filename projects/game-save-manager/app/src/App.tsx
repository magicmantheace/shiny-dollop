import { useState } from 'react';
import { SaveManagerProvider, useStore } from './store';
import GameLibrary from './components/GameLibrary';
import GameDetail from './components/GameDetail';
import SchedulesView from './components/SchedulesView';
import AddGameDialog from './components/AddGameDialog';
import Toasts from './components/Toasts';

type View = { name: 'library' } | { name: 'schedules' } | { name: 'game'; gameId: number };

function Shell(): React.ReactNode {
  const { games } = useStore();
  const [view, setView] = useState<View>({ name: 'library' });
  const [addOpen, setAddOpen] = useState(false);

  const selectedGame =
    view.name === 'game' ? (games.find((g) => g.id === view.gameId) ?? null) : null;

  return (
    <div className="gsm-root">
      <header className="gsm-header">
        <h1>Game Save Manager</h1>
        <nav aria-label="Main">
          <button
            type="button"
            className={`gsm-nav-btn${view.name !== 'schedules' ? ' gsm-nav-btn-active' : ''}`}
            onClick={() => setView({ name: 'library' })}
            aria-current={view.name !== 'schedules' ? 'page' : undefined}
          >
            Library
          </button>
          <button
            type="button"
            className={`gsm-nav-btn${view.name === 'schedules' ? ' gsm-nav-btn-active' : ''}`}
            onClick={() => setView({ name: 'schedules' })}
            aria-current={view.name === 'schedules' ? 'page' : undefined}
          >
            Schedules
          </button>
        </nav>
      </header>

      <main>
        {view.name === 'schedules' ? (
          <SchedulesView />
        ) : selectedGame ? (
          <GameDetail game={selectedGame} onBack={() => setView({ name: 'library' })} />
        ) : view.name === 'game' ? (
          <section className="gsm-view" aria-label="Game not found">
            <div className="gsm-error" role="alert">
              <strong>That game is no longer in the library.</strong>
            </div>
            <button type="button" className="gsm-btn" onClick={() => setView({ name: 'library' })}>
              Back to library
            </button>
          </section>
        ) : (
          <GameLibrary
            onSelectGame={(gameId) => setView({ name: 'game', gameId })}
            onAddGame={() => setAddOpen(true)}
          />
        )}
      </main>

      {addOpen && (
        <AddGameDialog
          onClose={() => setAddOpen(false)}
          onAdded={(gameId) => setView({ name: 'game', gameId })}
        />
      )}

      <Toasts />
    </div>
  );
}

export default function App(): React.ReactNode {
  return (
    <SaveManagerProvider>
      <Shell />
    </SaveManagerProvider>
  );
}
