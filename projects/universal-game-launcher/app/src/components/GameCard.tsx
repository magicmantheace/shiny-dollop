import { useState } from 'react';
import type { Game } from '../../shared/types';
import { ApiCallError, formatDateTime, formatDuration, getApi, unwrap } from '../api';

interface Props {
  game: Game;
  onChanged: () => void;
  onSelect: (game: Game) => void;
}

export default function GameCard({ game, onChanged, onSelect }: Props) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  async function toggleFavorite(e: React.MouseEvent) {
    e.stopPropagation();
    setError(null);
    try {
      await unwrap(getApi().library.setFavorite({ id: game.id, favorite: !game.favorite }));
      onChanged();
    } catch (err) {
      setError(err instanceof ApiCallError ? err.message : String(err));
    }
  }

  async function play(e: React.MouseEvent) {
    e.stopPropagation();
    if (busy) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const result = await unwrap(getApi().games.launch({ id: game.id }));
      if (result.alreadyRunning) {
        setError('Already running — showing the existing session.');
      } else if (game.source === 'steam') {
        setNotice(
          'Launch requested — handed to the Steam client. Playtime can\u2019t be tracked for store launches.',
        );
      } else if (game.source === 'epic') {
        setNotice(
          'Launch requested — Epic Games Launcher is opening. Pick your game there; playtime can\u2019t be tracked for store launches.',
        );
      }
      onChanged();
    } catch (err) {
      setError(err instanceof ApiCallError ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  const canPlay = !game.missing && game.launchCapability !== 'unavailable';
  const playLabel = busy
    ? 'Launching…'
    : game.source === 'steam'
      ? 'Play via Steam'
      : game.source === 'epic'
        ? 'Open Epic Games Launcher'
        : 'Play';

  return (
    <article
      className="card"
      onClick={() => onSelect(game)}
      onKeyDown={(e) => {
        if (e.key === 'Enter') onSelect(game);
      }}
      tabIndex={0}
      role="button"
      aria-label={`${game.title} details`}
    >
      <div className="card-top">
        <span className="card-title" title={game.title}>
          {game.title}
        </span>
        <button
          className={game.favorite ? 'star active' : 'star'}
          onClick={toggleFavorite}
          aria-label={game.favorite ? 'Remove from favorites' : 'Add to favorites'}
          aria-pressed={game.favorite}
          title={game.favorite ? 'Remove from favorites' : 'Add to favorites'}
        >
          ★
        </button>
      </div>
      <div className="card-meta">
        <span className="badge">{game.source}</span>
        {game.missing && <span className="badge warn">Missing</span>}
      </div>
      <div className="card-sub muted">
        {game.lastPlayedAt ? `Last played ${formatDateTime(game.lastPlayedAt)}` : 'Never played'}
        {game.totalPlayMs > 0 && ` · ${formatDuration(game.totalPlayMs)} tracked`}
      </div>
      <div className="card-actions">
        <button
          className="btn primary"
          onClick={play}
          disabled={busy || !canPlay}
          title={!canPlay && game.launchReason ? game.launchReason : undefined}
        >
          {playLabel}
        </button>
      </div>
      {game.launchCapability === 'unavailable' && game.launchReason && (
        <div className="card-error" role="alert">
          {game.launchReason}
        </div>
      )}
      {game.missing && (
        <div className="card-error" role="alert">
          {game.source === 'steam'
            ? 'Install folder not found — the game may have been moved or uninstalled via Steam.'
            : game.source === 'epic'
              ? 'Install folder not found — the game may have been moved or uninstalled via the Epic Games Launcher.'
              : 'File not found — it may have been moved, renamed or uninstalled.'}
        </div>
      )}
      {notice && (
        <div className="card-notice" role="status">
          {notice}
        </div>
      )}
      {error && (
        <div className="card-error" role="alert">
          {error}
        </div>
      )}
    </article>
  );
}
