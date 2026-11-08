import { useState } from 'react';
import { getGmm, type ImportRootsResult } from '../gmm';

interface Props {
  onChanged: () => void;
}

/** Imports games by scanning root folders, one path per line. */
export function ImportPanel({ onChanged }: Props) {
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ImportRootsResult | null>(null);

  const run = async () => {
    setError(null);
    setResult(null);
    const roots = text
      .split('\n')
      .map((line) => line.trim())
      .filter((line) => line !== '');
    if (roots.length === 0) {
      setError('Enter at least one root path, one per line.');
      return;
    }
    setBusy(true);
    try {
      const r = await getGmm().lib.importRoots(roots);
      setResult(r);
      onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const importedGames = result?.games ?? [];

  return (
    <section className="panel" aria-label="Import game library">
      <h2>Import game library</h2>
      <p className="muted">
        Enter the folders to scan for games, one path per line. Importing only
        reads folders and records metadata — it never modifies your games.
      </p>
      <div className="form-row">
        <label>
          Root paths
          <textarea
            className="input mono"
            rows={6}
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder={'C:\\Games\nD:\\More Games'}
            aria-label="Root paths, one per line"
          />
        </label>
      </div>
      <button className="btn btn-primary" onClick={run} disabled={busy}>
        {busy ? 'Importing…' : 'Import'}
      </button>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {result && (
        <div className="result-block" role="status">
          <p>
            Imported <strong>{result.imported}</strong>, skipped{' '}
            <strong>{result.skipped}</strong>.
          </p>
          {importedGames.length > 0 && (
            <ul className="name-list">
              {importedGames.map((g) => (
                <li key={g.id}>
                  <span>{g.title}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </section>
  );
}
