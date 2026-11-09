import { useEffect, useRef, useState } from 'react';
import type { EvidenceLabel, SaveCandidate } from '../../shared/types';
import { useStore } from '../store';
import { IpcError, unwrap } from '../api';
import { errorSummary } from '../errorMessages';
import SourceBadge from './SourceBadge';

const EVIDENCE_COPY: Record<EvidenceLabel, { label: string; note: string }> = {
  'verified-path': {
    label: 'Verified path',
    note: 'Found at a save location this store client is known to use.',
  },
  'pattern-match': {
    label: 'Pattern match — not confirmed',
    note: 'A folder name looks like this game, but this is only a guess. Check the path before adding.',
  },
  manual: {
    label: 'Manual',
    note: 'Added from a folder you picked yourself.',
  },
};

interface AddGameDialogProps {
  onClose: () => void;
  onAdded: (gameId: number) => void;
}

/**
 * Add-game dialog: name + native folder picker (games.chooseFolder), plus an
 * optional discovery scan whose candidates are always shown with their honest
 * evidence label — never presented as certain when they are not.
 */
export default function AddGameDialog({ onClose, onAdded }: AddGameDialogProps): React.ReactNode {
  const { addGame, pushToast } = useStore();
  const [name, setName] = useState('');
  const [savePath, setSavePath] = useState('');
  const [choosing, setChoosing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [candidates, setCandidates] = useState<SaveCandidate[] | null>(null);
  const [scanning, setScanning] = useState(false);
  const [scanError, setScanError] = useState<string | null>(null);
  const [addingCandidate, setAddingCandidate] = useState<number | null>(null);
  const nameRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    nameRef.current?.focus();
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent): void => {
      if (e.key === 'Escape') {
        onClose();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  const chooseFolder = async (): Promise<void> => {
    setChoosing(true);
    try {
      const res = unwrap(await window.saveManager.games.chooseFolder());
      if (res.path) {
        setSavePath(res.path);
        setFormError(null);
      }
    } catch (err) {
      setFormError(
        err instanceof IpcError ? errorSummary(err.code, err.message) : 'Could not open the folder picker.',
      );
    } finally {
      setChoosing(false);
    }
  };

  const scan = async (): Promise<void> => {
    setScanning(true);
    setScanError(null);
    try {
      setCandidates(unwrap(await window.saveManager.games.discoverCandidates()));
    } catch (err) {
      setScanError(
        err instanceof IpcError ? errorSummary(err.code, err.message) : 'Save-folder scan failed.',
      );
    } finally {
      setScanning(false);
    }
  };

  const submit = async (e: React.FormEvent): Promise<void> => {
    e.preventDefault();
    if (!name.trim()) {
      setFormError('Give the game a name.');
      return;
    }
    if (!savePath.trim()) {
      setFormError('Choose the folder that holds this game\u2019s saves.');
      return;
    }
    setSaving(true);
    setFormError(null);
    try {
      const game = await addGame(name.trim(), savePath.trim());
      onAdded(game.id);
      onClose();
    } catch (err) {
      setFormError(
        err instanceof IpcError ? errorSummary(err.code, err.message) : 'Could not add the game.',
      );
      setSaving(false);
    }
  };

  const addCandidate = async (index: number, candidate: SaveCandidate): Promise<void> => {
    setAddingCandidate(index);
    try {
      const game = await addGame(candidate.gameName, candidate.savePath, candidate.source);
      onAdded(game.id);
      onClose();
    } catch (err) {
      pushToast(
        'error',
        'Could not add game',
        err instanceof IpcError ? errorSummary(err.code, err.message) : 'Could not add the game.',
      );
      setAddingCandidate(null);
    }
  };

  return (
    <div className="gsm-modal-backdrop" onClick={onClose}>
      <div
        className="gsm-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="add-game-title"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 id="add-game-title">Add game</h2>

        <form onSubmit={(e) => void submit(e)}>
          <label className="gsm-field">
            <span>Game name</span>
            <input
              ref={nameRef}
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Elden Ring"
              maxLength={120}
            />
          </label>

          <div className="gsm-field">
            <label htmlFor="add-game-path">
              <span>Save folder</span>
            </label>
            <div className="gsm-field-row">
              <input
                id="add-game-path"
                type="text"
                value={savePath}
                onChange={(e) => setSavePath(e.target.value)}
                placeholder="Pick the folder that holds the save files"
                spellCheck={false}
              />
              <button
                type="button"
                className="gsm-btn"
                onClick={() => void chooseFolder()}
                disabled={choosing}
              >
                {choosing ? 'Choosing…' : 'Choose folder…'}
              </button>
            </div>
          </div>

          {formError && (
            <div className="gsm-error" role="alert">
              {formError}
            </div>
          )}

          <div className="gsm-modal-actions">
            <button type="button" className="gsm-btn" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="gsm-btn gsm-btn-primary" disabled={saving}>
              {saving ? 'Adding…' : 'Add game'}
            </button>
          </div>
        </form>

        <div className="gsm-discovery">
          <h3>Find save folders automatically</h3>
          <p className="gsm-muted">
            Scan your Steam and Epic libraries for save folders. Results are
            labeled by how confident we are — check the path before adding a guess.
          </p>
          <button
            type="button"
            className="gsm-btn"
            onClick={() => void scan()}
            disabled={scanning}
            aria-busy={scanning}
          >
            {scanning ? 'Scanning…' : 'Scan for save folders'}
          </button>

          {scanError && (
            <div className="gsm-error" role="alert">
              {scanError}
            </div>
          )}

          {candidates !== null && candidates.length === 0 && !scanning && (
            <p className="gsm-muted">No save folders found. Add the game manually above.</p>
          )}

          {candidates !== null && candidates.length > 0 && (
            <ul className="gsm-candidate-list">
              {candidates.map((c, i) => {
                const evidence = EVIDENCE_COPY[c.evidence];
                return (
                  <li key={`${c.source}-${c.savePath}-${i}`} className="gsm-candidate">
                    <div className="gsm-candidate-main">
                      <div className="gsm-candidate-title">
                        <strong>{c.gameName}</strong>
                        <SourceBadge source={c.source} />
                      </div>
                      <div className="gsm-candidate-path" title={c.savePath}>
                        {c.savePath}
                      </div>
                      <div className="gsm-candidate-evidence">
                        <span className={`gsm-evidence gsm-evidence-${c.evidence}`}>
                          {evidence.label}
                        </span>
                        <span className="gsm-muted">{c.detail || evidence.note}</span>
                      </div>
                    </div>
                    <button
                      type="button"
                      className="gsm-btn"
                      onClick={() => void addCandidate(i, c)}
                      disabled={addingCandidate !== null}
                    >
                      {addingCandidate === i ? 'Adding…' : 'Add'}
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
