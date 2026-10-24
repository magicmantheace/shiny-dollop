import { useState } from 'react';
import type { Game } from '../../shared/types';
import { parseArgsString } from '../../shared/args';
import { ApiCallError, formatDateTime, formatDuration, getApi, unwrap } from '../api';

interface Props {
  game: Game;
  onClose: () => void;
  onChanged: () => void;
}

/** Details / edit panel for one library entry. */
export default function GameDetails({ game, onClose, onChanged }: Props) {
  const [title, setTitle] = useState(game.title);
  const [workingDir, setWorkingDir] = useState(game.workingDir ?? '');
  const [argsText, setArgsText] = useState(game.args.join(' '));
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirmRemove, setConfirmRemove] = useState(false);
  const [coverPath, setCoverPath] = useState<string | null>(game.coverPath);

  async function chooseCover() {
    setBusy(true);
    setError(null);
    try {
      const picked = await unwrap(getApi().files.chooseCover());
      if ('canceled' in picked) return;
      await unwrap(getApi().library.update({ id: game.id, coverPath: picked.coverPath }));
      setCoverPath(picked.coverPath);
      onChanged();
    } catch (err) {
      setError(err instanceof ApiCallError ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function clearCover() {
    setBusy(true);
    setError(null);
    try {
      await unwrap(getApi().library.update({ id: game.id, coverPath: null }));
      setCoverPath(null);
      onChanged();
    } catch (err) {
      setError(err instanceof ApiCallError ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function save() {
    setBusy(true);
    setError(null);
    try {
      let args: string[];
      try {
        args = parseArgsString(argsText);
      } catch (e) {
        throw new Error((e as Error).message);
      }
      await unwrap(
        getApi().library.update({
          id: game.id,
          title: title.trim(),
          workingDir: workingDir.trim() === '' ? null : workingDir.trim(),
          args,
        }),
      );
      onChanged();
      onClose();
    } catch (err) {
      setError(err instanceof ApiCallError ? err.message : (err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    setBusy(true);
    setError(null);
    try {
      await unwrap(getApi().library.remove({ id: game.id }));
      onChanged();
      onClose();
    } catch (err) {
      setError(err instanceof ApiCallError ? err.message : String(err));
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
        aria-label={`${game.title} details`}
        onClick={(e) => e.stopPropagation()}
      >
        <h2>Game details</h2>
        <label>
          Title
          <input value={title} onChange={(e) => setTitle(e.target.value)} maxLength={256} autoFocus />
        </label>
        <label>
          Executable <span className="muted">(read-only)</span>
          <input value={game.exePath ?? '—'} readOnly disabled />
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
        <div className="cover-row">
          <span>
            Cover art{' '}
            <span className="muted">
              {coverPath ? '(custom)' : '(placeholder)'}
            </span>
          </span>
          <span className="cover-actions">
            <button className="btn" onClick={chooseCover} disabled={busy}>
              Choose image…
            </button>
            {coverPath && (
              <button className="btn" onClick={clearCover} disabled={busy}>
                Remove
              </button>
            )}
          </span>
        </div>
        <div className="detail-stats muted">
          <span>Added {formatDateTime(game.addedAt)}</span>
          <span>Last played {formatDateTime(game.lastPlayedAt)}</span>
          <span>Tracked {formatDuration(game.totalPlayMs)}</span>
        </div>
        {error && (
          <div className="form-error" role="alert">
            {error}
          </div>
        )}
        {!confirmRemove ? (
          <div className="modal-actions">
            <button className="btn primary" onClick={save} disabled={busy}>
              {busy ? 'Saving…' : 'Save changes'}
            </button>
            <button className="btn" onClick={onClose}>
              Cancel
            </button>
            <button className="btn danger" onClick={() => setConfirmRemove(true)}>
              Remove from library
            </button>
          </div>
        ) : (
          <div className="confirm-box" role="alert">
            <p>
              <strong>Remove "{game.title}" from your library?</strong>
            </p>
            <p>
              This only removes the entry from the launcher. It will <strong>not</strong>{' '}
              uninstall, delete, or modify any game files.
            </p>
            <div className="modal-actions">
              <button className="btn danger" onClick={remove} disabled={busy}>
                {busy ? 'Removing…' : 'Yes, remove it'}
              </button>
              <button className="btn" onClick={() => setConfirmRemove(false)}>
                Keep it
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
