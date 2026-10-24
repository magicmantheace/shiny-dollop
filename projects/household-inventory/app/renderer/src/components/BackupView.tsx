import { useState } from 'react';
import { styles, theme } from '../styles';

export default function BackupView() {
  const [exportResult, setExportResult] = useState<{ filePath: string; itemCount: number; attachmentCount: number } | null>(null);
  const [importResult, setImportResult] = useState<{ filePath: string; itemCount: number; attachmentCount: number } | null>(null);
  const [busy, setBusy] = useState<'export' | 'import' | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleExport() {
    setError(null);
    setBusy('export');
    try {
      const summary = await window.inv.backup.export();
      setExportResult({ filePath: summary.filePath, itemCount: summary.itemCount, attachmentCount: summary.attachmentCount });
      setImportResult(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  async function handleImport() {
    setError(null);
    setBusy('import');
    try {
      // The native file dialog runs in the main process; this call blocks
      // until the user picks a file or cancels.
      const summary = await window.inv.backup.import();
      setImportResult({ filePath: summary.filePath, itemCount: summary.itemCount, attachmentCount: summary.attachmentCount });
      setExportResult(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div>
      <div style={styles.card}>
        <h2 style={styles.cardTitle}>What a backup contains</h2>
        <p style={{ fontSize: '14px', marginTop: 0 }}>
          A backup file holds everything the app knows: the full inventory database (items, categories,
          maintenance events, warranty dates) <strong>plus</strong> every attachment (receipts, photos,
          manuals) and a checksum manifest so the file can be verified on restore. Nothing leaves your
          computer — the file is written to a path you can see, and import reads it back locally.
        </p>
        <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
          <button style={styles.button} onClick={handleExport} disabled={busy !== null}>
            {busy === 'export' ? 'Exporting…' : 'Export backup'}
          </button>
          <button style={styles.buttonSecondary} onClick={handleImport} disabled={busy !== null}>
            {busy === 'import' ? 'Waiting for file…' : 'Import backup'}
          </button>
        </div>
        <p style={styles.muted}>
          Import replaces all current data with the backup's contents. Before anything is replaced,
          the app saves your current state as a <strong>rollback-&lt;timestamp&gt;</strong> backup so a
          bad import can be undone.
        </p>
      </div>

      {error && <div style={styles.errorBox}>Backup failed: {error}</div>}

      {exportResult && (
        <div style={{ ...styles.banner, ...styles.bannerOk }}>
          Backup exported: {exportResult.filePath}
          <br />
          {exportResult.itemCount} item{exportResult.itemCount === 1 ? '' : 's'}, {exportResult.attachmentCount} attachment{exportResult.attachmentCount === 1 ? '' : 's'}.
        </div>
      )}

      {importResult && (
        <div>
          <div style={{ ...styles.banner, ...styles.bannerOk }}>
            Backup imported from: {importResult.filePath}
            <br />
            {importResult.itemCount} item{importResult.itemCount === 1 ? '' : 's'}, {importResult.attachmentCount} attachment{importResult.attachmentCount === 1 ? '' : 's'} restored.
          </div>
          <div style={{ ...styles.banner, ...styles.bannerWarn, border: `1px solid ${theme.warn}` }}>
            Your previous data was rolled back to a backup named <strong>rollback-&lt;timestamp&gt;</strong> before
            this import. If anything looks wrong, re-import that rollback file to restore it.
          </div>
        </div>
      )}
    </div>
  );
}
