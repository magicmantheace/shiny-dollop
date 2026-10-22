import { useMemo, useState } from 'react';
import type { Game, SortKey } from '../../shared/types';
import EmptyState from '../components/EmptyState';
import GameCard from '../components/GameCard';
import GameDetails from '../components/GameDetails';

interface Props {
  games: Game[];
  onRefresh: () => void;
  onAdd: () => void;
}

const SORT_LABELS: Record<SortKey, string> = {
  title: 'A–Z',
  added: 'Recently added',
  lastPlayed: 'Last played',
  playtime: 'Most played',
};

export default function LibraryPage({ games, onRefresh, onAdd }: Props) {
  const [search, setSearch] = useState('');
  const [sort, setSort] = useState<SortKey>('title');
  const [selected, setSelected] = useState<Game | null>(null);

  const visible = useMemo(() => {
    const q = search.trim().toLowerCase();
    const filtered = q
      ? games.filter((g) => g.title.toLowerCase().includes(q))
      : games.slice();
    const by: Record<SortKey, (a: Game, b: Game) => number> = {
      title: (a, b) => a.title.localeCompare(b.title),
      added: (a, b) => b.addedAt.localeCompare(a.addedAt),
      lastPlayed: (a, b) => (b.lastPlayedAt ?? '').localeCompare(a.lastPlayedAt ?? ''),
      playtime: (a, b) => b.totalPlayMs - a.totalPlayMs,
    };
    return filtered.sort(by[sort]);
  }, [games, search, sort]);

  return (
    <section aria-label="Library">
      <div className="page-head">
        <h1>Library</h1>
        <div className="toolbar">
          <input
            className="search"
            type="search"
            placeholder="Search games…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            aria-label="Search games"
          />
          <select
            value={sort}
            onChange={(e) => setSort(e.target.value as SortKey)}
            aria-label="Sort games"
          >
            {(Object.keys(SORT_LABELS) as SortKey[]).map((k) => (
              <option key={k} value={k}>
                {SORT_LABELS[k]}
              </option>
            ))}
          </select>
        </div>
      </div>
      {games.length === 0 ? (
        <EmptyState
          title="No games yet"
          body="No games yet — Add a game or scan launchers."
          actionLabel="Add a game"
          onAction={onAdd}
        />
      ) : visible.length === 0 ? (
        <EmptyState title="No matches" body={`Nothing in your library matches "${search}".`} />
      ) : (
        <div className="grid">
          {visible.map((g) => (
            <GameCard key={g.id} game={g} onChanged={onRefresh} onSelect={setSelected} />
          ))}
        </div>
      )}
      {selected && (
        <GameDetails
          game={selected}
          onClose={() => setSelected(null)}
          onChanged={onRefresh}
        />
      )}
    </section>
  );
}
