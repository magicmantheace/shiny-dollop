import { useEffect, useRef, useState } from 'react';
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

function sameIds(a: string[], b: string[]): boolean {
  return a.length === b.length && a.every((v, i) => v === b[i]);
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

  // The last persisted snapshot this draft was reconciled against. App keeps
  // this view mounted under the same game-id key across refreshes, so the
  // useState initializers above never re-run when the persisted game changes
  // underneath us (header Undo, bundle import, our own save). Without
  // reconciliation the form would keep showing — and a later Save would
  // resurrect — values the database no longer holds.
  const lastPersistedRef = useRef<Game>(game);

  // Field-level reconciliation: a field whose draft still equals the previous
  // persisted value is clean, so it adopts the new persisted value; a field
  // the user has edited since (draft differs from the previous persisted
  // value) is dirty and is left alone. That is what lets an undo of a just-
  // saved title sync the form (the draft equalled the saved value) while an
  // artwork-only / missing-flag refresh — which changes no persisted field —
  // never discards unsaved edits.
  useEffect(() => {
    const prev = lastPersistedRef.current;
    if (prev.id !== game.id) {
      lastPersistedRef.current = game;
      setTitle(game.title);
      setDescription(game.description);
      setTagIds(game.tagIds);
      setCollectionIds(game.collectionIds);
      setArtworkId(game.artworkId);
      return;
    }
    const persistedChanged =
      prev.updatedAt !== game.updatedAt ||
      prev.title !== game.title ||
      prev.description !== game.description ||
      prev.artworkId !== game.artworkId ||
      !sameIds(prev.tagIds, game.tagIds) ||
      !sameIds(prev.collectionIds, game.collectionIds);
    if (!persistedChanged) return;
    setTitle((cur) => (cur === prev.title ? game.title : cur));
    setDescription((cur) => (cur === prev.description ? game.description : cur));
    setTagIds((cur) => (sameIds(cur, prev.tagIds) ? game.tagIds : cur));
    setCollectionIds((cur) => (sameIds(cur, prev.collectionIds) ? game.collectionIds : cur));
    setArtworkId((cur) => (cur === prev.artworkId ? game.artworkId : cur));
    lastPersistedRef.current = game;
  }, [game]);

  // Merge refreshed artwork into the local list instead of replacing it, so
  // artwork added in this view (not yet in the prop on the first refresh) is
  // not dropped, and refreshed metadata for known artwork wins.
  useEffect(() => {
    setLocalArtworks((prevLocal) => {
      const incomingIds = new Set(artworks.map((a) => a.id));
      const localOnly = prevLocal.filter((a) => !incomingIds.has(a.id));
      const next = [...artworks, ...localOnly];
      return next.length === prevLocal.length && next.every((a, i) => a === prevLocal[i])
        ? prevLocal
        : next;
    });
  }, [artworks]);

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
  }, [game.id, game.updatedAt]);

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
      const savedGame = await getGmm().game.update(game.id, {
        title: title.trim(),
        description,
        artworkId,
        tagIds,
        collectionIds,
      });
      // The draft is now exactly the persisted snapshot; recording it means a
      // later undo (which reverts the persisted values) is recognised as a
      // clean-field change and syncs back into the form.
      if (savedGame) lastPersistedRef.current = savedGame;
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
