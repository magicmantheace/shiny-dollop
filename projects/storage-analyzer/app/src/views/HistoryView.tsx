import { useEffect, useState } from 'react';
import { api, friendlyErrorMessage, unwrap } from '../api';
import { formatBytes, formatDateTime, formatInt } from '../format';
import type { ScanState, ScanSummaryInfo } from '../types';

export interface HistoryViewProps {
  onSelectScan: (scanId: number) => void;
  onError: (message: string) => void;
}

const STATE_BADGE: Record<ScanState, string> = {
  running: 'badge badge-running',
  cancelled: 'badge badge-cancelled',
  complete: 'badge badge-complete',
  failed: 'badge badge-failed',
};

/** History view: past scans with state badges; click one to view its results. */
export function HistoryView({ onSelectScan, onError }: HistoryViewProps) {
  const [scans, setScans] = useState<ScanSummaryInfo[] | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      try {
        const { scans: list } = unwrap(await api().scan.list());
        if (!cancelled) {
          setScans([...list].sort((a, b) => (a.startedAt < b.startedAt ? 1 : -1)));
        }
      } catch (err) {
        if (!cancelled) {
          onError(friendlyErrorMessage(err));
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [onError]);

  if (loading) {
    return (
      <section aria-labelledby="history-heading">
        <h2 id="history-heading">Scan history</h2>
        <p>Loading history…</p>
      </section>
    );
  }

  return (
    <section aria-labelledby="history-heading">
      <h2 id="history-heading">Scan history</h2>
      {scans !== null && scans.length === 0 && <p>No scans yet.</p>}
      <ul className="history-list">
        {(scans ?? []).map((scan) => (
          <li key={scan.id}>
            <button
              type="button"
              className="history-item"
              onClick={() => onSelectScan(scan.id)}
              aria-label={`View results for scan of ${scan.rootPath} started ${formatDateTime(scan.startedAt)}`}
            >
              <span className={STATE_BADGE[scan.state]}>{scan.state}</span>
              <span className="history-path" title={scan.rootPath}>
                {scan.rootPath}
              </span>
              <span className="history-meta">
                {formatInt(scan.files)} files · {formatBytes(scan.bytes)} · {formatDateTime(scan.startedAt)}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
