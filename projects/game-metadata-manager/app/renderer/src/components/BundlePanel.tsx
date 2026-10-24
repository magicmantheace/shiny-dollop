import { useState } from 'react';
import { getGmm, type BundleImportResult } from '../gmm';
import { UndoButton } from './UndoButton';

interface Props {
  onChanged: () => void;
}

/** Minimal typing for the File System Access API save picker, when present. */
interface SavePickerHandle {
  createWritable(): Promise<{
    write(data: string): Promise<void>;
    close(): Promise<void>;
  }>;
}
type WindowWithSavePicker = Window & {
  showSaveFilePicker?: (options?: Record<string, unknown>) => Promise<SavePickerHandle>;
};

export function BundlePanel({ onChanged }: Props) {
  const [json, setJson] = useState<string | null>(null);
  const [exportBusy, setExportBusy] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [saveMsg, setSaveMsg] = useState<string | null>(null);

  const [importText, setImportText] = useState('');
  const [importBusy, setImportBusy] = useState(false);
  const [importError, setImportError] = useState<string | null>(null);
  const [importResult, setImportResult] = useState<BundleImportResult | null>(null);

  const canNativeSave = (window as unknown as WindowWithSavePicker).showSaveFilePicker !== undefined;

  const doExport = async () => {
    setExportBusy(true);
    setExportError(null);
    setCopied(false);
    setSaveMsg(null);
    try {
      const { json: text } = await getGmm().bundle.export();
      setJson(text ?? '');
    } catch (err) {
      setExportError(err instanceof Error ? err.message : String(err));
    } finally {
      setExportBusy(false);
    }
  };

  const copyJson = async () => {
    if (json === null) return;
    try {
      if (!navigator.clipboard) throw new Error('Clipboard API is not available.');
      await navigator.clipboard.writeText(json);
      setCopied(true);
    } catch (err) {
      setExportError(err instanceof Error ? err.message : String(err));
    }
  };

  const saveToFile = async () => {
    if (json === null) return;
    const picker = (window as unknown as WindowWithSavePicker).showSaveFilePicker;
    if (!picker) {
      setSaveMsg('Native save dialog is not available here — copy the JSON above instead.');
      return;
    }
    try {
      const handle = await picker({
        suggestedName: 'game-metadata-bundle.json',
        types: [{ description: 'JSON', accept: { 'application/json': ['.json'] } }],
      });
      const writable = await handle.createWritable();
      await writable.write(json);
      await writable.close();
      setSaveMsg('Bundle saved to file.');
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') {
        setSaveMsg('Save cancelled.');
      } else {
        setSaveMsg(err instanceof Error ? err.message : String(err));
      }
    }
  };

  const doImport = async () => {
    setImportError(null);
    setImportResult(null);
    if (importText.trim() === '') {
      setImportError('Paste bundle JSON first.');
      return;
    }
    setImportBusy(true);
    try {
      const result = await getGmm().bundle.import(importText);
      setImportResult(result);
      onChanged();
    } catch (err) {
      setImportError(err instanceof Error ? err.message : String(err));
    } finally {
      setImportBusy(false);
    }
  };

  return (
    <section className="panel" aria-label="Metadata bundles">
      <h2>Metadata bundles</h2>
      <p className="muted">
        Bundles are portable JSON snapshots of your metadata. Importing one merges
        it in and reports every conflict instead of silently overwriting.
      </p>

      <div className="form-block">
        <h3>Export</h3>
        <button className="btn" onClick={doExport} disabled={exportBusy}>
          {exportBusy ? 'Exporting…' : 'Export bundle'}
        </button>
        {exportError && (
          <p className="error" role="alert">
            {exportError}
          </p>
        )}
        {json !== null && (
          <>
            <div className="form-row">
              <label>
                Bundle JSON
                <textarea
                  className="input mono"
                  rows={10}
                  readOnly
                  value={json}
                  aria-label="Exported bundle JSON"
                />
              </label>
            </div>
            <div className="form-row inline">
              <button className="btn" onClick={copyJson}>
                Copy to clipboard
              </button>
              <button className="btn" onClick={saveToFile} disabled={!canNativeSave}>
                Save to file…
              </button>
            </div>
            {!canNativeSave && (
              <p className="muted small">
                Native file saving is not available in this environment — use copy instead.
              </p>
            )}
            {copied && (
              <p className="notice" role="status">
                Copied to clipboard.
              </p>
            )}
            {saveMsg && (
              <p className="notice" role="status">
                {saveMsg}
              </p>
            )}
          </>
        )}
      </div>

      <div className="form-block">
        <h3>Import</h3>
        <div className="form-row">
          <label>
            Bundle JSON
            <textarea
              className="input mono"
              rows={8}
              value={importText}
              onChange={(e) => setImportText(e.target.value)}
              placeholder='Paste a bundle exported earlier, e.g. {"version":1,…}'
              aria-label="Bundle JSON to import"
            />
          </label>
        </div>
        <button className="btn btn-primary" onClick={doImport} disabled={importBusy}>
          {importBusy ? 'Importing…' : 'Import bundle'}
        </button>
        {importError && (
          <p className="error" role="alert">
            {importError}
          </p>
        )}
        {importResult && (
          <div className="result-block" role="status">
            <p>
              Imported <strong>{importResult.added}</strong> new{' '}
              {importResult.added === 1 ? 'game' : 'games'},{' '}
              <strong>{importResult.updated}</strong> updated.
            </p>
            {importResult.conflicts.length > 0 ? (
              <>
                <h4>Conflicts ({importResult.conflicts.length})</h4>
                <table className="table">
                  <thead>
                    <tr>
                      <th>Game</th>
                      <th>Field</th>
                      <th>Kept</th>
                      <th>Bundle value</th>
                      <th>Winner</th>
                    </tr>
                  </thead>
                  <tbody>
                    {importResult.conflicts.map((c, i) => (
                      <tr key={`${c.gameId}:${c.field}:${i}`}>
                        <td>{c.gameId}</td>
                        <td>{c.field}</td>
                        <td>{c.localValue}</td>
                        <td>{c.bundleValue}</td>
                        <td>
                          <span className="badge">{c.chosen}</span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </>
            ) : (
              <p className="muted small">No conflicts.</p>
            )}
          </div>
        )}
      </div>

      <div className="form-block">
        <h3>Undo</h3>
        <UndoButton onUndone={onChanged} />
      </div>
    </section>
  );
}
