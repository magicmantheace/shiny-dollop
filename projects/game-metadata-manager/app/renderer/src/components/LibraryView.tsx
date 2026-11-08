import { useMemo, useState } from 'react';
import { getGmm, type Collection, type Game, type Tag } from '../gmm';
import { ArtworkThumb } from './ArtworkThumb';

interface Props {
  games: Game[];
  tags: Tag[];
  collections: Collection[];
  onSelect: (gameId: string) => void;
  onChanged: () => void;
}

export function LibraryView({ games, tags, collections, onSelect, onChanged }: Props) {
  const [query, setQuery] = useState('');
  const [tagId, setTagId] = useState('');
  const [collectionId, setCollectionId] = useState('');
  const [missingOnly, setMissingOnly] = useState(false);
  const [rescanning, setRescanning] = useState(false);
  const [rescanMsg, setRescanMsg] = useState<string | null>(null);
  const [rescanError, setRescanError] = useState<string | null>(null);

  const tagNameById = useMemo(() => new Map(tags.map((t) => [t.id, t.name])), [tags]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return games.filter((g) => {
      if (missingOnly && !g.missing) return false;
      if (tagId !== '' && !g.tagIds.includes(tagId)) return false;
      if (collectionId !== '' && !g.collectionIds.includes(collectionId)) return false;
      if (q !== '' && !`${g.title} ${g.originalTitle}`.toLowerCase().includes(q)) return false;
      return true;
    });
  }, [games, query, tagId, collectionId, missingOnly]);

  const rescan = async () => {
    setRescanning(true);
    setRescanMsg(null);
    setRescanError(null);
    try {
      const { missingIds } = await getGmm().lib.rescan();
      const n = missingIds?.length ?? 0;
      setRescanMsg(
        n === 0
          ? 'Rescan complete — every install path was found.'
          : `Rescan complete — ${n} missing install${n === 1 ? '' : 's'} detected.`,
      );
      onChanged();
    } catch (err) {
      setRescanError(err instanceof Error ? err.message : String(err));
    } finally {
      setRescanning(false);
    }
  };

  return (
    <section className="panel" aria-label="Game library">
      <div className="toolbar" role="search">
        <input
          className="input"
          type="search"
          placeholder="Search titles…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          aria-label="Search games"
        />
        <select
          className="input"
          value={tagId}
          onChange={(e) => setTagId(e.target.value)}
          aria-label="Filter by tag"
        >
          <option value="">All tags</option>
          {tags.map((t) => (
            <option key={t.id} value={t.id}>
              {t.name}
            </option>
          ))}
        </select>
        <select
          className="input"
          value={collectionId}
          onChange={(e) => setCollectionId(e.target.value)}
          aria-label="Filter by collection"
        >
          <option value="">All collections</option>
          {collections.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
        <label className="check">
          <input
            type="checkbox"
            checked={missingOnly}
            onChange={(e) => setMissingOnly(e.target.checked)}
          />
          Missing only
        </label>
        <button className="btn" onClick={rescan} disabled={rescanning}>
          {rescanning ? 'Rescanning…' : 'Detect missing installs'}
        </button>
      </div>

      {rescanMsg && (
        <p className="notice" role="status">
          {rescanMsg}
        </p>
      )}
      {rescanError && (
        <p className="error" role="alert">
          {rescanError}
        </p>
      )}

      <p className="muted" aria-live="polite">
        {filtered.length} of {games.length} games
      </p>

      <ul className="game-list">
        {filtered.map((g) => (
          <li key={g.id}>
            <button className="game-item" onClick={() => onSelect(g.id)}>
              <ArtworkThumb artworkId={g.artworkId} title={g.title} size={56} />
              <span className="game-item-body">
                <span className="game-item-title">
                  {g.title}
                  {g.missing && <span className="badge badge-missing">MISSING</span>}
                </span>
                {g.originalTitle !== '' && g.originalTitle !== g.title && (
                  <span className="muted small">Original title: {g.originalTitle}</span>
                )}
                {g.tagIds.length > 0 && (
                  <span className="chips">
                    {g.tagIds.map((tid) => (
                      <span key={tid} className="chip">
                        {tagNameById.get(tid) ?? tid}
                      </span>
                    ))}
                  </span>
                )}
              </span>
            </button>
          </li>
        ))}
      </ul>
      {filtered.length === 0 && <p className="muted">No games match these filters.</p>}
    </section>
  );
}
