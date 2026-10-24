import { useRef, useState } from 'react';
import { readFileAsText } from '../lib/file';
import { getPkv, type BackupImportResult } from '../types';
import { styles } from '../styles';

/**
 * The canonical backup.import returns { imported, skipped }; per-record
 * validation problems surface as thrown errors. Some backends may also
 * return an `errors` array — displayed when present (forward-compatible).
 */
type ImportResultView = BackupImportResult & { errors?: string[] };

function countNotesInPayload(payload: string): number | null {
  try {
    const parsed = JSON.parse(payload) as { notes?: unknown };
    return Array.isArray(parsed.notes) ? parsed.notes.length : null;
  } catch {
    return null;
  }
}

export default function BackupView() {
  const [exportBusy, setExportBusy] = useState(false);
  const [exportMessage, setExportMessage] = useState<string | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);

  const [importBusy, setImportBusy] = useState(false);
  const [importResult, setImportResult] = useState<ImportResultView | null>(null);
  const [importError, setImportError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const runExport = async () => {
    setExportBusy(true);
    setExportMessage(null);
    setExportError(null);
    try {
      // The main process builds the payload AND shows the save dialog;
      // the renderer receives the JSON payload string.
      const payload = await getPkv().backup.export();
      const count = countNotesInPayload(payload);
      setExportMessage(
        count === null
          ? 'Backup prepared. The app showed a save dialog for the file.'
          : `Backup prepared with ${count} note${count === 1 ? '' : 's'}. The app showed a save dialog for the file.`,
      );
    } catch (err: unknown) {
      setExportError(err instanceof Error ? err.message : 'Export failed.');
    } finally {
      setExportBusy(false);
    }
  };

  const runImport = async (file: File) => {
    setImportBusy(true);
    setImportResult(null);
    setImportError(null);
    try {
      const payload = await readFileAsText(file);
      if (payload.trim().length === 0) {
        setImportError('The selected file is empty.');
        return;
      }
      const result = (await getPkv().backup.import(payload)) as ImportResultView;
      setImportResult(result);
    } catch (err: unknown) {
      setImportError(err instanceof Error ? err.message : 'Import failed.');
    } finally {
      setImportBusy(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  return (
    <section aria-label="Backup">
      <h2 style={styles.h2}>Backup</h2>
      <p style={styles.muted}>
        Export a portable JSON backup of the vault (notes, sources, review status and
        revision history), or restore one from a file. Nothing leaves this machine.
      </p>

      <div style={styles.panel} aria-label="Export backup">
        <h3 style={styles.h3}>Export</h3>
        {exportError && (
          <div style={styles.alertError} role="alert">
            {exportError}
          </div>
        )}
        {exportMessage && (
          <div style={styles.alertOk} role="status">
            {exportMessage}
          </div>
        )}
        <button
          type="button"
          style={{ ...styles.buttonPrimary, ...(exportBusy ? styles.buttonDisabled : {}) }}
          disabled={exportBusy}
          onClick={runExport}
        >
          {exportBusy ? 'Exporting…' : 'Export backup'}
        </button>
      </div>

      <div style={styles.panel} aria-label="Import backup">
        <h3 style={styles.h3}>Import</h3>
        {importError && (
          <div style={styles.alertError} role="alert">
            {importError}
          </div>
        )}
        {importResult && (
          <div
            style={
              (importResult.errors?.length ?? 0) > 0 ? styles.alertError : styles.alertOk
            }
            role="status"
            aria-label="Import result"
          >
            <p style={{ margin: '0 0 8px 0' }}>
              Imported {importResult.imported} note
              {importResult.imported === 1 ? '' : 's'}, skipped {importResult.skipped}.
            </p>
            {(importResult.errors?.length ?? 0) > 0 && (
              <>
                <p style={{ margin: '0 0 4px 0', fontWeight: 700 }}>
                  Validation errors ({importResult.errors?.length}):
                </p>
                <ul style={{ margin: 0, paddingLeft: '20px' }}>
                  {importResult.errors?.map((e, i) => (
                    <li key={i}>{e}</li>
                  ))}
                </ul>
              </>
            )}
          </div>
        )}
        <label htmlFor="backup-file" style={styles.label}>
          Backup file (.json)
        </label>
        <input
          ref={fileInputRef}
          id="backup-file"
          type="file"
          accept=".json,application/json"
          disabled={importBusy}
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) {
              void runImport(file);
            }
          }}
        />
        {importBusy && <p style={styles.muted}>Importing…</p>}
      </div>
    </section>
  );
}
