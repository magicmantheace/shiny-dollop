import { useState } from 'react';
import { api, friendlyErrorMessage, unwrap } from '../api';
import { DEFAULT_EXCLUSIONS, isProtectedPath, parseExclusions } from '../format';
import type { ScanStartWarning } from '../types';

export interface StartViewProps {
  onScanStarted: (scanId: number, startWarning?: ScanStartWarning) => void;
  onError: (message: string) => void;
}

/**
 * Start view: pick a directory (native dialog), edit exclusion patterns,
 * see a protected-path warning, and kick off a scan.
 */
export function StartView({ onScanStarted, onError }: StartViewProps) {
  const [rootPath, setRootPath] = useState('');
  const [exclusions, setExclusions] = useState(DEFAULT_EXCLUSIONS);
  const [starting, setStarting] = useState(false);

  const protectedPath = rootPath !== '' && isProtectedPath(rootPath);

  async function chooseDirectory() {
    try {
      const result = unwrap(await api().dialog.chooseDirectory());
      if (result.path) {
        setRootPath(result.path);
      }
    } catch (err) {
      onError(friendlyErrorMessage(err));
    }
  }

  async function startScan() {
    if (!rootPath || starting) {
      return;
    }
    setStarting(true);
    try {
      const { scanId, warning } = unwrap(
        await api().scan.start({ rootPath, exclusions: parseExclusions(exclusions) }),
      );
      onScanStarted(scanId, warning);
    } catch (err) {
      onError(friendlyErrorMessage(err));
      setStarting(false);
    }
  }

  return (
    <section aria-labelledby="start-heading">
      <h2 id="start-heading">New scan</h2>

      <div className="field">
        <label htmlFor="root-path">Folder to scan</label>
        <div className="input-row">
          <input
            id="root-path"
            type="text"
            readOnly
            value={rootPath}
            placeholder="No folder selected"
            aria-describedby={protectedPath ? 'protected-warning' : undefined}
          />
          <button type="button" onClick={chooseDirectory}>
            Choose folder…
          </button>
        </div>
      </div>

      {protectedPath && (
        <div id="protected-warning" className="warning-banner" role="alert">
          <strong>Protected path warning:</strong> this looks like a drive root or a Windows
          system folder. Scanning it can be slow and hit permission errors. The scan is
          read-only and will never modify files, but consider picking a smaller folder.
        </div>
      )}

      <div className="field">
        <label htmlFor="exclusions">Exclusion patterns (one per line)</label>
        <textarea
          id="exclusions"
          rows={4}
          value={exclusions}
          onChange={(e) => setExclusions(e.target.value)}
          aria-describedby="exclusions-hint"
        />
        <p id="exclusions-hint" className="hint">
          Folders whose name matches any pattern are skipped during the scan.
        </p>
      </div>

      <button type="button" onClick={startScan} disabled={!rootPath || starting} className="primary">
        {starting ? 'Starting…' : 'Start scan'}
      </button>
    </section>
  );
}
