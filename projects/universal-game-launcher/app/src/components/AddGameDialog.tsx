import { useState } from 'react';
import { parseArgsString } from '../../shared/args';
import { ApiCallError, basenameOf, dirnameOf, getApi, unwrap } from '../api';

interface Props {
  onClose: () => void;
  onAdded: () => void;
}

function stripExt(name: string): string {
  const i = name.lastIndexOf('.');
  return i > 0 ? name.slice(0, i) : name;
}

export default function AddGameDialog({ onClose, onAdded }: Props) {
  const [exePath, setExePath] = useState<string | null>(null);
  const [title, setTitle] = useState('');
  const [workingDir, setWorkingDir] = useState('');
  const [argsText, setArgsText] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function choose() {
    setError(null);
    try {
      const result = await unwrap(getApi().files.chooseExecutable());
      if ('canceled' in result && result.canceled) return;
      const picked = (result as { path: string }).path;
      setExePath(picked);
      setTitle((t) => (t === '' ? stripExt(basenameOf(picked)) : t));
      setWorkingDir((w) => (w === '' ? dirnameOf(picked) : w));
    } catch (err) {
      setError(err instanceof ApiCallError ? err.message : String(err));
    }
  }

  async function add() {
    if (!exePath) {
      setError('Choose an executable first.');
      return;
    }
    setBusy(true);
    setError(null);
    try {
      let args: string[];
      try {
        args = parseArgsString(argsText);
      } catch (e) {
        throw new Error((e as Error).message);
      }
      const input: { path: string; workingDir?: string; args: string[] } = {
        path: exePath,
        args,
      };
      const wd = workingDir.trim();
      if (wd !== '') input.workingDir = wd;
      await unwrap(getApi().library.addManual(input));
      onAdded();
    } catch (err) {
      setError(
        err instanceof ApiCallError ? err.message : err instanceof Error ? err.message : String(err),
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="modal-backdrop" onClick={onClose} role="presentation">
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-label="Add a game"
        onClick={(e) => e.stopPropagation()}
      >
        <h2>Add a game</h2>
        <p className="muted">
          Pick a trusted executable on this PC. It stays where it is — the launcher only
          remembers where to find it.
        </p>
        <div className="field-row">
          <input value={exePath ?? ''} readOnly placeholder="No file chosen yet" aria-label="Chosen executable" />
          <button className="btn" onClick={choose} autoFocus>
            Choose…
          </button>
        </div>
        <label>
          Title
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            maxLength={256}
            placeholder="Game title"
          />
        </label>
        <label>
          Working directory <span className="muted">(optional)</span>
          <input
            value={workingDir}
            onChange={(e) => setWorkingDir(e.target.value)}
            placeholder="Defaults to the executable's folder"
          />
        </label>
        <label>
          Launch arguments <span className="muted">(optional)</span>
          <input
            value={argsText}
            onChange={(e) => setArgsText(e.target.value)}
            placeholder='e.g. --fullscreen --level 3'
          />
        </label>
        {error && (
          <div className="form-error" role="alert">
            {error}
          </div>
        )}
        <div className="modal-actions">
          <button className="btn primary" onClick={add} disabled={busy || !exePath}>
            {busy ? 'Adding…' : 'Add game'}
          </button>
          <button className="btn" onClick={onClose}>
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
