import { useState } from 'react';
import { getGmm, type Artwork } from '../gmm';

interface Props {
  onAdded: (artwork: Artwork) => void;
}

/** Adds an artwork entry from a local file path plus free-text provenance. */
export function ArtworkAddForm({ onAdded }: Props) {
  const [sourcePath, setSourcePath] = useState('');
  const [provenance, setProvenance] = useState('');
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    setError(null);
    const path = sourcePath.trim();
    if (path === '') {
      setError('Enter a file path for the artwork.');
      return;
    }
    setAdding(true);
    try {
      const artwork = await getGmm().artwork.add(path, provenance.trim());
      setSourcePath('');
      setProvenance('');
      onAdded(artwork);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setAdding(false);
    }
  };

  return (
    <div className="form-block">
      <h3>Add artwork from file</h3>
      <div className="form-row">
        <label>
          File path
          <input
            className="input"
            type="text"
            value={sourcePath}
            onChange={(e) => setSourcePath(e.target.value)}
            placeholder="C:\Games\art\cover.png"
            aria-label="Artwork file path"
          />
        </label>
      </div>
      <div className="form-row">
        <label>
          Provenance
          <input
            className="input"
            type="text"
            value={provenance}
            onChange={(e) => setProvenance(e.target.value)}
            placeholder="e.g. scanned from the retail box"
            aria-label="Artwork provenance"
          />
        </label>
      </div>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      <button className="btn" onClick={submit} disabled={adding}>
        {adding ? 'Adding…' : 'Add artwork'}
      </button>
    </div>
  );
}
