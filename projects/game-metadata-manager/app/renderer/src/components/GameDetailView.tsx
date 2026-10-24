import { useEffect, useState } from 'react';
import {
  getGmm,
  type Artwork,
  type ChangeEntry,
  type Collection,
  type Game,
  type Tag,
} from '../gmm';
import { ArtworkThumb } from './ArtworkThumb';
import { ArtworkAddForm } from './ArtworkAddForm';

interface Props {
  game: Game;
  tags: Tag[];
  collections: Collection[];
  artworks: Artwork[];
  onBack: () => void;
  onChanged: () => void;
}

function toggleId(list: string[], id: string): string[] {
  return list.includes(id) ? list.filter((x) => x !== id) : [...list, id];
}

export function GameDetailView({ game, tags, collections, artworks, onBack, onChanged }: Props) {
  const [title, setTitle] = useState(game.title);
  const [description, setDescription] = useState(game.description);
  const [tagIds, setTagIds] = useState<string[]>(game.tagIds);
  const [collectionIds, setCollectionIds] = useState<string[]>(game.collectionIds);
  const [artworkId, setArtworkId] = useState<string | null>(game.artworkId);
  const [localArtworks, setLocalArtworks] = useState<Artwork[]>(artworks);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [history, setHistory] = useState<ChangeEntry[]>([]);
  const [historyError, setHistoryError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getGmm().changes.list(game.id).then(
      (entries) => {
        if (!cancelled) setHistory(entries ?? []);
      },
      (err: unknown) => {
        if (!cancelled) setHistoryError(err instanceof Error ? err.message : String(err));
      },
    );
    return () => {
      cancelled = true;
    };
  }, [game.id]);

  const currentArtwork = localArtworks.find((a) => a.id === artworkId) ?? null;

  const save = async () => {
    setError(null);
    setSaved(false);
    if (title.trim() === '') {
      setError('Title cannot be empty.');
      return;
    }
    setSaving(true);
    try {
      await getGmm().game.update(game.id, {
        title: title.trim(),
        description,
        artworkId,
        tagIds,
        collectionIds,
      });
      setSaved(true);
      onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="panel" aria-label={`Details for ${game.title}`}>
      <button className="btn btn-ghost" onClick={onBack}>
        ← Back to library
      </button>

      {game.missing && (
        <p className="banner-warning" role="alert">
          Install not found at: <code>{game.installPath}</code>
          <br />
          The metadata below is kept as-is; nothing was deleted.
        </p>
      )}

      <div className="form-row">
        <label>
          Title
          <input
            className="input"
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            aria-label="Game title"
          />
        </label>
      </div>

      <div className="form-row">
        <label>
          Original title <span className="muted small">(read-only)</span>
          <input className="input" type="text" value={game.originalTitle} readOnly aria-label="Original title" />
        </label>
      </div>

      <div className="form-row">
        <label>
          Description
          <textarea
            className="input"
            rows={4}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            aria-label="Game description"
          />
        </label>
      </div>

      <fieldset className="check-group">
        <legend>Tags</legend>
        {tags.length === 0 && <p className="muted small">No tags yet — add some under “Tags &amp; Collections”.</p>}
        {tags.map((t) => (
          <label key={t.id} className="check">
            <input
              type="checkbox"
              checked={tagIds.includes(t.id)}
              onChange={() => setTagIds((ids) => toggleId(ids, t.id))}
            />
            {t.name}
          </label>
        ))}
      </fieldset>

      <fieldset className="check-group">
        <legend>Collections</legend>
        {collections.length === 0 && (
          <p className="muted small">No collections yet — add some under “Tags &amp; Collections”.</p>
        )}
        {collections.map((c) => (
          <label key={c.id} className="check">
            <input
              type="checkbox"
              checked={collectionIds.includes(c.id)}
              onChange={() => setCollectionIds((ids) => toggleId(ids, c.id))}
            />
            {c.name}
          </label>
        ))}
      </fieldset>

      <fieldset className="check-group">
        <legend>Artwork</legend>
        <div className="artwork-picker">
          <label className="artwork-option">
            <input
              type="radio"
              name="artwork"
              checked={artworkId === null}
              onChange={() => setArtworkId(null)}
            />
            <ArtworkThumb artworkId={null} title={game.title} size={72} />
            <span className="muted small">No artwork</span>
          </label>
          {localArtworks.map((a) => (
            <label key={a.id} className="artwork-option">
              <input
                type="radio"
                name="artwork"
                checked={artworkId === a.id}
                onChange={() => setArtworkId(a.id)}
              />
              <ArtworkThumb artworkId={a.id} title={game.title} size={72} />
              <span className="artwork-meta">
                <span>{a.fileName}</span>
                <span className="muted small">{a.provenance}</span>
              </span>
            </label>
          ))}
        </div>
        {currentArtwork && (
          <p className="muted small">
            Provenance: {currentArtwork.provenance} · {currentArtwork.mime}
          </p>
        )}
        <ArtworkAddForm
          onAdded={(art) => {
            setLocalArtworks((prev) => [...prev, art]);
            setArtworkId(art.id);
            onChanged();
          }}
        />
      </fieldset>

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {saved && (
        <p className="notice" role="status">
          Saved.
        </p>
      )}
      <div className="form-row">
        <button className="btn btn-primary" onClick={save} disabled={saving}>
          {saving ? 'Saving…' : 'Save changes'}
        </button>
      </div>

      <div className="form-block">
        <h3>Change history</h3>
        {historyError && (
          <p className="error" role="alert">
            {historyError}
          </p>
        )}
        {!historyError && history.length === 0 && (
          <p className="muted small">No recorded changes for this game yet.</p>
        )}
        {history.length > 0 && (
          <table className="table">
            <thead>
              <tr>
                <th>When</th>
                <th>Field</th>
                <th>Before</th>
                <th>After</th>
              </tr>
            </thead>
            <tbody>
              {history.map((h) => (
                <tr key={h.id}>
                  <td>{h.at}</td>
                  <td>{h.field}</td>
                  <td>{h.before}</td>
                  <td>{h.after}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  );
}
