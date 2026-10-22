import { useMemo, useState } from 'react';
import type { Game, GameSource, SortKey } from '../../shared/types';
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

const SOURCE_FILTERS: Array<{ value: '' | GameSource; label: string }> = [
  { value: '', label: 'All sources' },
  { value: 'manual', label: 'Manual' },
  { value: 'steam', label: 'Steam' },
  { value: 'epic', label: 'Epic Games' },
  { value: 'battlenet', label: 'Battle.net' },
];

export default function LibraryPage({ games, onRefresh, onAdd }: Props) {
  const [search, setSearch] = useState('');
  const [sort, setSort] = useState<SortKey>('title');
  const [sourceFilter, setSourceFilter] = useState<'' | GameSource>('');
  const [selected, setSelected] = useState<Game | null>(null);

  const visible = useMemo(() => {
    const q = search.trim().toLowerCase();
    let filtered = games;
    if (sourceFilter) filtered = filtered.filter((g) => g.source === sourceFilter);
    if (q) filtered = filtered.filter((g) => g.title.toLowerCase().includes(q));
    const by: Record<SortKey, (a: Game, b: Game) => number> = {
      title: (a, b) => a.title.localeCompare(b.title),
      added: (a, b) => b.addedAt.localeCompare(a.addedAt),
      lastPlayed: (a, b) => (b.lastPlayedAt ?? '').localeCompare(a.lastPlayedAt ?? ''),
      playtime: (a, b) => b.totalPlayMs - a.totalPlayMs,
    };
    return filtered.slice().sort(by[sort]);
  }, [games, search, sort, sourceFilter]);

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
          <select
            value={sourceFilter}
            onChange={(e) => setSourceFilter(e.target.value as '' | GameSource)}
            aria-label="Filter by source"
          >
            {SOURCE_FILTERS.map((f) => (
              <option key={f.label} value={f.value}>
                {f.label}
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
