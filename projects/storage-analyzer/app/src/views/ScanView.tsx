import { useCallback, useEffect, useRef, useState } from 'react';
import { api, friendlyErrorMessage, unwrap } from '../api';
import { formatBytes, formatDateTime, formatInt } from '../format';
import type {
  ScanFinishedEvent,
  ScanProgressEvent,
  ScanStartWarning,
  ScanState,
  ScanStatus,
} from '../types';

export interface ScanViewProps {
  scanId: number;
  startWarning?: ScanStartWarning | undefined;
  onViewResults: (scanId: number) => void;
  onNewScan: () => void;
  onError: (message: string) => void;
}

/**
 * Scan view: live progress counters, current path, cancel button.
 * Listens for scan.progress / scan.finished events and also polls
 * scan.status so a finished state always resolves even if an event is missed.
 */
export function ScanView({ scanId, startWarning, onViewResults, onNewScan, onError }: ScanViewProps) {
  const [status, setStatus] = useState<ScanStatus | null>(null);
  const [currentPath, setCurrentPath] = useState('');
  const [cancelling, setCancelling] = useState(false);
  const [cancellingFailed, setCancellingFailed] = useState(false);
  const scanIdRef = useRef(scanId);
  scanIdRef.current = scanId;

  const terminal = status !== null && status.state !== 'running';

  const refresh = useCallback(async () => {
    try {
      const next = unwrap(await api().scan.status({ scanId: scanIdRef.current }));
      setStatus(next);
    } catch (err) {
      onError(friendlyErrorMessage(err));
    }
  }, [onError]);

  useEffect(() => {
    let cancelled = false;

    void refresh();

    const offProgress = api().onProgress((event: ScanProgressEvent) => {
      if (cancelled || event.scanId !== scanIdRef.current) {
        return;
      }
      setCurrentPath(event.currentPath);
      setStatus((prev) => ({
        state: 'running',
        files: event.files,
        dirs: event.dirs,
        bytes: event.bytes,
        errors: prev?.errors ?? 0,
        changedFiles: prev?.changedFiles ?? 0,
        startedAt: prev?.startedAt ?? new Date().toISOString(),
        finishedAt: null,
      }));
    });

    const offFinished = api().onFinished((event: ScanFinishedEvent) => {
      if (cancelled || event.scanId !== scanIdRef.current) {
        return;
      }
      // Re-read the authoritative status; the event only carries the state.
      void refresh();
    });

    const timer = window.setInterval(() => {
      void refresh();
    }, 2000);

    return () => {
      cancelled = true;
      offProgress();
      offFinished();
      window.clearInterval(timer);
    };
  }, [scanId, refresh]);

  async function cancelScan() {
    setCancelling(true);
    setCancellingFailed(false);
    try {
      unwrap(await api().scan.cancel({ scanId }));
      await refresh();
    } catch (err) {
      setCancellingFailed(true);
      onError(friendlyErrorMessage(err));
    } finally {
      setCancelling(false);
    }
  }

  const stateLabel: Record<ScanState, string> = {
    running: 'Scanning…',
    cancelled: 'Scan cancelled',
    complete: 'Scan complete',
    failed: 'Scan failed',
  };

  return (
    <section aria-labelledby="scan-heading">
      <h2 id="scan-heading">Scan</h2>

      {startWarning === 'protected-path' && (
        <div className="warning-banner" role="alert">
          <strong>Protected path:</strong> the scanner flagged this folder as sensitive. The scan
          is read-only and skips anything it cannot read.
        </div>
      )}

      <div aria-live="polite" className="status-card">
        <p className="status-line">
          <strong>Status:</strong> {status ? stateLabel[status.state] : 'Connecting…'}
        </p>
        <dl className="counters">
          <div>
            <dt>Files</dt>
            <dd>{formatInt(status?.files ?? 0)}</dd>
          </div>
          <div>
            <dt>Folders</dt>
            <dd>{formatInt(status?.dirs ?? 0)}</dd>
          </div>
          <div>
            <dt>Bytes</dt>
            <dd>{formatBytes(status?.bytes ?? 0)}</dd>
          </div>
        </dl>
        <div className="progress-bar" role="progressbar" aria-label="Scan progress">
          <div className={status && status.state === 'running' ? 'bar indeterminate' : 'bar'} />
        </div>
        <p className="current-path" title={currentPath}>
          {currentPath || ' '}
        </p>
        {status?.error && (
          <p className="error-text" role="alert">
            Error: {status.error}
          </p>
        )}
        {status && (status.errors > 0 || status.changedFiles > 0) && (
          <p className="meta">
            Skipped entries: {formatInt(status.errors)} · files changed mid-scan:{' '}
            {formatInt(status.changedFiles)}
          </p>
        )}
        {status?.startedAt && <p className="meta">Started: {formatDateTime(status.startedAt)}</p>}
      </div>

      <div className="actions">
        {!terminal && (
          <button type="button" onClick={cancelScan} disabled={cancelling} className="danger">
            {cancelling ? 'Cancelling…' : 'Cancel scan'}
          </button>
        )}
        {terminal && (
          <>
            <button type="button" onClick={() => onViewResults(scanId)} className="primary">
              View results
            </button>
            <button type="button" onClick={onNewScan}>
              New scan
            </button>
          </>
        )}
      </div>
      {cancellingFailed && (
        <p className="error-text" role="alert">
          Cancel failed; the scan may already have finished. Refreshing status…
        </p>
      )}
    </section>
  );
}
