import { useEffect, useState } from 'react';
import type { GameSource, Settings, SourceStatus } from '../../shared/types';
import { ApiCallError, formatDateTime, getApi, unwrap } from '../api';

interface Props {
  settings: Settings;
  onRefresh: () => void;
}

const SOURCE_LABELS: Record<GameSource, string> = {
  manual: 'Manual entries',
  steam: 'Steam',
  epic: 'Epic Games',
  battlenet: 'Battle.net',
};

export default function SettingsPage({ settings, onRefresh }: Props) {
  const [sources, setSources] = useState<SourceStatus[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [scanning, setScanning] = useState<GameSource | null>(null);
  const [scanNote, setScanNote] = useState<string | null>(null);

  async function loadSources() {
    try {
      setSources(await unwrap(getApi().sources.status()));
    } catch (err: unknown) {
      setError(err instanceof ApiCallError ? err.message : String(err));
    }
  }

  useEffect(() => {
    void loadSources();
  }, []);

  async function scan(source: GameSource) {
    setScanning(source);
    setScanNote(null);
    setError(null);
    try {
      const result = await unwrap(getApi().sources.scan({ source }));
      setScanNote(
        `Scanned ${new Date(result.scannedAt).toLocaleString()} — ${result.gamesFound} game(s) in the library.`,
      );
      await loadSources();
      onRefresh();
    } catch (err) {
      setError(err instanceof ApiCallError ? err.message : String(err));
    } finally {
      setScanning(null);
    }
  }

  async function cancelScan() {
    try {
      await unwrap(getApi().sources.cancelScan());
      setScanNote('Cancellation requested.');
    } catch (err) {
      setError(err instanceof ApiCallError ? err.message : String(err));
    } finally {
      setScanning(null);
    }
  }

  async function update(patch: Partial<Settings>) {
    setBusy(true);
    setError(null);
    try {
      await unwrap(getApi().settings.update(patch));
      onRefresh();
    } catch (err) {
      setError(err instanceof ApiCallError ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-label="Settings">
      <div className="page-head">
        <h1>Settings</h1>
      </div>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      <div className="settings-group">
        <h2>Playback</h2>
        <label className="check">
          <input
            type="checkbox"
            checked={settings.trackingEnabled}
            disabled={busy}
            onChange={(e) => update({ trackingEnabled: e.target.checked })}
          />
          Track play sessions
          <span className="muted"> — record start/end times for launched games. Turn off for privacy.</span>
        </label>
        <label className="check">
          <input
            type="checkbox"
            checked={settings.minimizeOnLaunch}
            disabled={busy}
            onChange={(e) => update({ minimizeOnLaunch: e.target.checked })}
          />
          Minimize launcher when a game starts
        </label>
        <label>
          Theme
          <select
            value={settings.theme}
            disabled={busy}
            onChange={(e) => update({ theme: e.target.value as Settings['theme'] })}
          >
            <option value="dark">Dark</option>
            <option value="light">Light</option>
            <option value="system">System</option>
          </select>
        </label>
      </div>
      <div className="settings-group">
        <h2>Game sources</h2>
        {sources.map((s) => (
          <div key={s.source} className="source-row">
            <span className="source-name">{SOURCE_LABELS[s.source]}</span>
            <span className={`badge ${s.available ? '' : 'warn'}`}>
              {s.source === 'steam' ? (s.available ? 'Detected' : 'Not found') : s.available ? 'Ready' : 'Not yet available'}
            </span>
            <span className="muted">{s.reason}</span>
            <span className="muted">
              {s.gamesFound} in library
              {s.lastScanAt ? ` · last scan ${formatDateTime(s.lastScanAt)}` : ''}
            </span>
            {s.source === 'steam' &&
              (scanning === 'steam' ? (
                <button className="btn" onClick={cancelScan}>
                  Cancel scan
                </button>
              ) : (
                <button className="btn" onClick={() => scan('steam')} disabled={scanning !== null}>
                  Scan now
                </button>
              ))}
          </div>
        ))}
        {scanNote && (
          <p className="card-notice" role="status">
            {scanNote}
          </p>
        )}
      </div>
      <div className="settings-group">
        <h2>About</h2>
        <p className="muted">
          Universal Game Launcher 0.1.0 — your library lives in this PC's app data folder. No
          account, no telemetry.
        </p>
      </div>
    </section>
  );
}
