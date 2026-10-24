import { useEffect, useState } from 'react';
import type { Backup, BackupDetail as BackupDetailT, Game, VerifyBackupResult } from '../../shared/types';
import { IpcError, unwrap } from '../api';
import { errorSummary } from '../errorMessages';
import { formatBytes, formatDateTime } from '../format';
import RestoreDialog from './RestoreDialog';

interface BackupDetailProps {
  backup: Backup;
  game: Game;
}

/**
 * Selected backup: file list with SHA-256 checksums and sizes, a Verify button
 * with per-file ok/corrupt results, and the Restore flow.
 */
export default function BackupDetail({ backup, game }: BackupDetailProps): React.ReactNode {
  const [detail, setDetail] = useState<BackupDetailT | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [verifying, setVerifying] = useState(false);
  const [verifyResult, setVerifyResult] = useState<VerifyBackupResult | null>(null);
  const [verifyError, setVerifyError] = useState<string | null>(null);
  const [restoreOpen, setRestoreOpen] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setVerifyResult(null);
    setVerifyError(null);
    window.saveManager.backups
      .get({ backupId: backup.id })
      .then((res) => {
        if (!cancelled) {
          setDetail(unwrap(res));
          setLoading(false);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(
            err instanceof IpcError ? errorSummary(err.code, err.message) : 'Could not load backup details.',
          );
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [backup.id]);

  const verify = async (): Promise<void> => {
    setVerifying(true);
    setVerifyError(null);
    setVerifyResult(null);
    try {
      setVerifyResult(unwrap(await window.saveManager.backups.verify({ backupId: backup.id })));
    } catch (err) {
      setVerifyError(
        err instanceof IpcError ? errorSummary(err.code, err.message) : 'Verification failed.',
      );
    } finally {
      setVerifying(false);
    }
  };

  if (loading) {
    return (
      <div className="gsm-backup-detail" aria-busy="true">
        <p className="gsm-muted">Loading backup contents…</p>
      </div>
    );
  }

  if (error || !detail) {
    return (
      <div className="gsm-backup-detail">
        <div className="gsm-error" role="alert">
          {error ?? 'Could not load backup details.'}
        </div>
      </div>
    );
  }

  const okCount = verifyResult ? verifyResult.checkedFiles - verifyResult.corrupt.length : null;

  return (
    <div className="gsm-backup-detail">
      <div className="gsm-backup-detail-meta">
        <span className="gsm-muted">
          Created {formatDateTime(detail.createdAt)} · {detail.fileCount} file
          {detail.fileCount === 1 ? '' : 's'} · {formatBytes(detail.totalBytes)}
        </span>
        {detail.notes && <span className="gsm-note-text">Notes: {detail.notes}</span>}
      </div>

      <div className="gsm-detail-actions">
        <button type="button" className="gsm-btn" onClick={() => void verify()} disabled={verifying}>
          {verifying ? 'Verifying…' : 'Verify'}
        </button>
        <button type="button" className="gsm-btn gsm-btn-warning" onClick={() => setRestoreOpen(true)}>
          Restore…
        </button>
      </div>

      {verifyError && (
        <div className="gsm-error" role="alert">
          {verifyError}
        </div>
      )}

      {verifyResult && (
        <div
          className={`gsm-verify ${verifyResult.ok ? 'gsm-verify-ok' : 'gsm-verify-bad'}`}
          role="status"
          aria-label="Verification result"
        >
          {verifyResult.ok ? (
            <strong>✓ All {verifyResult.checkedFiles} files verified — checksums match.</strong>
          ) : (
            <>
              <strong>
                ⚠ {verifyResult.corrupt.length} of {verifyResult.checkedFiles} files failed verification:
              </strong>
              <ul>
                {verifyResult.corrupt.map((c) => (
                  <li key={c.relPath}>
                    <code>{c.relPath}</code> —{' '}
                    {c.issue === 'missing'
                      ? 'file is missing from the backup'
                      : c.issue === 'checksum-mismatch'
                        ? `checksum mismatch (expected ${c.expected ?? '?'}, got ${c.actual ?? '?'})`
                        : `size mismatch (expected ${c.expected ?? '?'}, got ${c.actual ?? '?'})`}
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}

      <table className="gsm-file-table">
        <caption className="gsm-sr-only">Files in this backup</caption>
        <thead>
          <tr>
            <th scope="col">File</th>
            <th scope="col">Size</th>
            <th scope="col">SHA-256</th>
            {verifyResult && <th scope="col">Status</th>}
          </tr>
        </thead>
        <tbody>
          {detail.files.map((f) => {
            const corrupt = verifyResult?.corrupt.find((c) => c.relPath === f.relPath);
            return (
              <tr key={f.relPath}>
                <td>
                  <code title={f.relPath}>{f.relPath}</code>
                </td>
                <td>{formatBytes(f.sizeBytes)}</td>
                <td>
                  <code className="gsm-hash" title={f.sha256}>
                    {f.sha256.slice(0, 16)}…
                  </code>
                </td>
                {verifyResult && (
                  <td>{corrupt ? <span className="gsm-bad">Corrupt</span> : <span className="gsm-good">OK</span>}</td>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>
      {verifyResult && okCount !== null && (
        <p className="gsm-muted">
          {okCount} of {verifyResult.checkedFiles} files OK.
        </p>
      )}

      {restoreOpen && (
        <RestoreDialog backup={backup} game={game} onClose={() => setRestoreOpen(false)} />
      )}
    </div>
  );
}
