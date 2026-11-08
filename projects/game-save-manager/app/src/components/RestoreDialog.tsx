import { useEffect, useRef, useState } from 'react';
import type { Backup, Game, RestoreBackupResult } from '../../shared/types';
import { IpcError, unwrap } from '../api';
import { errorSummary } from '../errorMessages';
import { formatDateTime } from '../format';

interface RestoreDialogProps {
  backup: Backup;
  game: Game;
  onClose: () => void;
}

type Phase = 'confirm' | 'restoring' | 'done';

/**
 * Restore flow:
 *  1. States up front that a pre-restore safety backup is taken first.
 *  2. Requires explicit confirmation — the user must type RESTORE; there is no
 *     pre-checked box anywhere.
 *  3. Calls backups.restore with confirmed: true (literally), then shows the
 *     post-restore verification result.
 */
export default function RestoreDialog({ backup, game, onClose }: RestoreDialogProps): React.ReactNode {
  const [confirmation, setConfirmation] = useState('');
  const [phase, setPhase] = useState<Phase>('confirm');
  const [result, setResult] = useState<RestoreBackupResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent): void => {
      if (e.key === 'Escape' && phase === 'confirm') {
        onClose();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose, phase]);

  const confirmed = confirmation.trim() === 'RESTORE';

  const doRestore = async (): Promise<void> => {
    if (!confirmed || phase !== 'confirm') {
      return;
    }
    setPhase('restoring');
    setError(null);
    try {
      // confirmed: true is sent literally — the backend rejects anything else.
      const res = unwrap(await window.saveManager.backups.restore({ backupId: backup.id, confirmed: true }));
      setResult(res);
      setPhase('done');
    } catch (err) {
      setError(
        err instanceof IpcError ? errorSummary(err.code, err.message) : 'Restore failed.',
      );
      setPhase('confirm');
    }
  };

  const backupName = backup.label ?? formatDateTime(backup.createdAt);

  return (
    <div className="gsm-modal-backdrop" onClick={phase === 'confirm' ? onClose : undefined}>
      <div
        className="gsm-modal gsm-modal-danger"
        role="dialog"
        aria-modal="true"
        aria-labelledby="restore-title"
        onClick={(e) => e.stopPropagation()}
      >
        {phase !== 'done' ? (
          <>
            <h2 id="restore-title">Restore backup?</h2>
            <p>
              You are about to restore <strong>“{backupName}”</strong> for{' '}
              <strong>{game.name}</strong>. This will overwrite the current save
              files in <code className="gsm-path-inline">{game.savePath}</code>.
            </p>
            <p className="gsm-safety-note">
              A <strong>pre-restore safety backup</strong> of your current saves
              will be taken automatically first, so you can undo this restore.
            </p>

            {error && (
              <div className="gsm-error" role="alert">
                {error}
              </div>
            )}

            <label className="gsm-field" htmlFor="restore-confirm">
              <span>
                To confirm, type <code>RESTORE</code> in the box below:
              </span>
              <input
                ref={inputRef}
                id="restore-confirm"
                type="text"
                value={confirmation}
                onChange={(e) => setConfirmation(e.target.value)}
                placeholder="Type RESTORE to confirm"
                autoComplete="off"
                disabled={phase === 'restoring'}
              />
            </label>

            <div className="gsm-modal-actions">
              <button type="button" className="gsm-btn" onClick={onClose} disabled={phase === 'restoring'}>
                Cancel
              </button>
              <button
                type="button"
                className="gsm-btn gsm-btn-danger"
                onClick={() => void doRestore()}
                disabled={!confirmed || phase === 'restoring'}
                aria-disabled={!confirmed}
              >
                {phase === 'restoring' ? 'Restoring…' : 'Restore backup'}
              </button>
            </div>
          </>
        ) : (
          <>
            <h2 id="restore-title">Restore complete</h2>
            {result && (
              <div role="status">
                <p>
                  Restored <strong>{result.restoredFiles}</strong> file
                  {result.restoredFiles === 1 ? '' : 's'} from <strong>“{backupName}”</strong> to{' '}
                  {game.name}.
                </p>
                <p className="gsm-safety-note">
                  A safety backup of your previous saves was kept
                  {result.safetyBackupId ? ` (backup #${result.safetyBackupId})` : ''} — you can
                  restore it the same way if anything looks wrong.
                </p>
                {result.mismatches.length === 0 ? (
                  <p className="gsm-good">
                    <strong>✓ Post-restore verification passed:</strong> all restored files match
                    the backup checksums.
                  </p>
                ) : (
                  <div className="gsm-verify gsm-verify-bad" role="alert">
                    <strong>
                      ⚠ Post-restore verification found {result.mismatches.length} mismatch
                      {result.mismatches.length === 1 ? '' : 'es'}:
                    </strong>
                    <ul>
                      {result.mismatches.map((m) => (
                        <li key={m.relPath}>
                          <code>{m.relPath}</code> — {m.issue}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
            <div className="gsm-modal-actions">
              <button type="button" className="gsm-btn gsm-btn-primary" onClick={onClose} autoFocus>
                Done
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
