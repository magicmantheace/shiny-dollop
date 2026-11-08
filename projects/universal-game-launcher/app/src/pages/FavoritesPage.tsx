import { useState } from 'react';
import type { Game } from '../../shared/types';
import EmptyState from '../components/EmptyState';
import GameCard from '../components/GameCard';
import GameDetails from '../components/GameDetails';

interface Props {
  games: Game[];
  onRefresh: () => void;
  onAdd: () => void;
}

export default function FavoritesPage({ games, onRefresh, onAdd }: Props) {
  const [selected, setSelected] = useState<Game | null>(null);
  const favorites = games.filter((g) => g.favorite);

  return (
    <section aria-label="Favorites">
      <div className="page-head">
        <h1>Favorites</h1>
      </div>
      {favorites.length === 0 ? (
        games.length === 0 ? (
          <EmptyState
            title="No favorites yet"
            body="Star a game to pin it here for quick access."
            actionLabel="Add a game"
            onAction={onAdd}
          />
        ) : (
          <EmptyState
            title="No favorites yet"
            body="Star a game to pin it here for quick access."
          />
        )
      ) : (
        <div className="grid">
          {favorites.map((g) => (
            <GameCard key={g.id} game={g} onChanged={onRefresh} onSelect={setSelected} />
          ))}
        </div>
      )}
      {selected && (
        <GameDetails game={selected} onClose={() => setSelected(null)} onChanged={onRefresh} />
      )}
    </section>
  );
}
