import { useStore } from '../store';
import { formatDateTime } from '../format';
import SourceBadge from './SourceBadge';

/**
 * Game library: rows of tracked games with backup counts and last-backup time,
 * plus an empty state with a clear "Add game" call to action.
 */
export default function GameLibrary({
  onSelectGame,
  onAddGame,
}: {
  onSelectGame: (gameId: number) => void;
  onAddGame: () => void;
}): React.ReactNode {
  const { games, gamesLoading, gamesError, gameStats, refreshGames } = useStore();

  if (gamesLoading) {
    return (
      <section className="gsm-view" aria-busy="true" aria-label="Game library">
        <p className="gsm-muted">Loading your game library…</p>
      </section>
    );
  }

  if (gamesError) {
    return (
      <section className="gsm-view" aria-label="Game library">
        <div className="gsm-error" role="alert">
          <strong>Couldn&apos;t load the game library.</strong>
          <p>{gamesError}</p>
          <button type="button" className="gsm-btn" onClick={() => void refreshGames()}>
            Retry
          </button>
        </div>
      </section>
    );
  }

  if (games.length === 0) {
    return (
      <section className="gsm-view gsm-empty" aria-label="Game library">
        <h2>No games tracked yet</h2>
        <p className="gsm-muted">
          Add a game and point to its save folder — Game Save Manager will back
          up your saves so you never lose progress.
        </p>
        <button type="button" className="gsm-btn gsm-btn-primary" onClick={onAddGame}>
          Add game
        </button>
      </section>
    );
  }

  return (
    <section className="gsm-view" aria-label="Game library">
      <div className="gsm-view-header">
        <h2>Game library</h2>
        <button type="button" className="gsm-btn gsm-btn-primary" onClick={onAddGame}>
          Add game
        </button>
      </div>
      <ul className="gsm-game-list">
        {games.map((game) => {
          const stats = gameStats[game.id];
          return (
            <li key={game.id}>
              <button
                type="button"
                className="gsm-game-row"
                onClick={() => onSelectGame(game.id)}
                aria-label={`Open ${game.name}`}
              >
                <span className="gsm-game-row-main">
                  <span className="gsm-game-row-title">
                    <strong>{game.name}</strong>
                    <SourceBadge source={game.source} />
                  </span>
                  <span className="gsm-game-row-path" title={game.savePath}>
                    {game.savePath}
                  </span>
                </span>
                <span className="gsm-game-row-stats">
                  <span>
                    {stats ? `${stats.backupCount} backup${stats.backupCount === 1 ? '' : 's'}` : '…'}
                  </span>
                  <span className="gsm-muted">
                    {stats && stats.lastBackupAt
                      ? `Last backup ${formatDateTime(stats.lastBackupAt)}`
                      : 'No backups yet'}
                  </span>
                </span>
                <span className="gsm-game-row-chevron" aria-hidden="true">
                  ›
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
