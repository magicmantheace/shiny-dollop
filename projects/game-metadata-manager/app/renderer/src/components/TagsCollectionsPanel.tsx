import { useState } from 'react';
import { getGmm, type Collection, type Tag } from '../gmm';

interface Props {
  tags: Tag[];
  collections: Collection[];
  onChanged: () => void;
}

interface NamedItem {
  id: string;
  name: string;
}

function EditableNameList({
  title,
  items,
  itemLabel,
  onAdd,
  onRemove,
}: {
  title: string;
  items: NamedItem[];
  itemLabel: string;
  onAdd: (name: string) => Promise<void>;
  onRemove: (id: string) => Promise<void>;
}) {
  const [name, setName] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const add = async () => {
    setError(null);
    if (name.trim() === '') {
      setError(`${itemLabel} name cannot be empty.`);
      return;
    }
    setBusy(true);
    try {
      await onAdd(name.trim());
      setName('');
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const remove = async (id: string) => {
    setError(null);
    setBusy(true);
    try {
      await onRemove(id);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="form-block">
      <h3>{title}</h3>
      <ul className="name-list">
        {items.map((item) => (
          <li key={item.id}>
            <span>{item.name}</span>
            <button
              className="btn btn-ghost btn-small"
              onClick={() => void remove(item.id)}
              disabled={busy}
              aria-label={`Remove ${itemLabel.toLowerCase()} ${item.name}`}
            >
              Remove
            </button>
          </li>
        ))}
      </ul>
      {items.length === 0 && <p className="muted small">None yet.</p>}
      <div className="form-row inline">
        <input
          className="input"
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder={`New ${itemLabel.toLowerCase()} name`}
          aria-label={`New ${itemLabel.toLowerCase()} name`}
        />
        <button className="btn" onClick={add} disabled={busy}>
          {busy ? 'Working…' : `Add ${itemLabel.toLowerCase()}`}
        </button>
      </div>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}

export function TagsCollectionsPanel({ tags, collections, onChanged }: Props) {
  const gmm = () => getGmm();
  return (
    <section className="panel" aria-label="Tags and collections">
      <h2>Tags &amp; collections</h2>
      <EditableNameList
        title="Tags"
        items={tags}
        itemLabel="Tag"
        onAdd={async (name) => {
          await gmm().tags.add(name);
          onChanged();
        }}
        onRemove={async (id) => {
          await gmm().tags.remove(id);
          onChanged();
        }}
      />
      <EditableNameList
        title="Collections"
        items={collections}
        itemLabel="Collection"
        onAdd={async (name) => {
          await gmm().collections.add(name);
          onChanged();
        }}
        onRemove={async (id) => {
          await gmm().collections.remove(id);
          onChanged();
        }}
      />
    </section>
  );
}
