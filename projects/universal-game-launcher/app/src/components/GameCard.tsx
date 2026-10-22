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
    try {
      const result = await unwrap(getApi().games.launch({ id: game.id }));
      if (result.alreadyRunning) {
        setError('Already running — showing the existing session.');
      }
      onChanged();
    } catch (err) {
      setError(err instanceof ApiCallError ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

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
        <button className="btn primary" onClick={play} disabled={busy || game.missing}>
          {busy ? 'Launching…' : 'Play'}
        </button>
      </div>
      {game.missing && (
        <div className="card-error" role="alert">
          File not found — it may have been moved, renamed or uninstalled.
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
