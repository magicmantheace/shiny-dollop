import { useState } from 'react';
import type {
  ExportFormat,
  ExportResult,
  LicenseRecord,
  TemplateManifest,
} from '../../shared/types';
import { api, errorText } from '../api';

interface ExportPanelProps {
  docId: string;
  manifest: TemplateManifest;
  /** Focus the field editor for the given manifest field key. */
  onSelectErrorField: (fieldKey: string) => void;
}

/** Split a `CODE:detail` error string into its named parts. */
export function parseExportError(error: string): { code: string; detail: string } {
  const idx = error.indexOf(':');
  if (idx === -1) return { code: error, detail: '' };
  return { code: error.slice(0, idx), detail: error.slice(idx + 1) };
}

/**
 * Export flow: choose a format, generate, inspect the license record and
 * content hash, then save. Backend validation failures are listed as named
 * errors, each linking to the offending field.
 */
export function ExportPanel({ docId, manifest, onSelectErrorField }: ExportPanelProps) {
  const [format, setFormat] = useState<ExportFormat>('html');
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<ExportResult | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  const [savedPath, setSavedPath] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveBusy, setSaveBusy] = useState(false);

  async function handleExport() {
    setBusy(true);
    setResult(null);
    setFailure(null);
    setSavedPath(null);
    setSaveError(null);
    try {
      setResult(await api.generateExport(docId, format));
    } catch (err) {
      setFailure(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleSave(html: string) {
    setSaveBusy(true);
    setSaveError(null);
    setSavedPath(null);
    try {
      const suggestedName = `${manifest.templateId}.${format === 'print' ? 'print.' : ''}html`;
      const res = await api.saveExport(html, suggestedName);
      if (res.canceled) {
        setSaveError('Save dialog was cancelled — no file was written.');
      } else {
        setSavedPath(res.filePath ?? '(path not reported)');
      }
    } catch (err) {
      setSaveError(errorText(err));
    } finally {
      setSaveBusy(false);
    }
  }

  const succeeded = result !== null && result.ok && typeof result.html === 'string';

  return (
    <section aria-labelledby="export-heading" className="export-panel">
      <h2 id="export-heading">Export</h2>

      <div className="export-controls" role="radiogroup" aria-label="Export format">
        {(['html', 'print'] as const).map((f) => (
          <label key={f} className="radio-label">
            <input
              type="radio"
              name="export-format"
              value={f}
              checked={format === f}
              disabled={busy}
              onChange={() => setFormat(f)}
            />
            {f === 'html' ? 'HTML' : 'Print'}
          </label>
        ))}
        <button
          type="button"
          className="btn btn-primary"
          disabled={busy}
          onClick={() => void handleExport()}
        >
          {busy ? 'Generating…' : 'Generate export'}
        </button>
      </div>

      {failure && (
        <p role="alert" className="alert alert-error">
          Export failed: <code>{failure}</code>
        </p>
      )}

      {result !== null && !result.ok && (
        <div role="alert" className="alert alert-error">
          <p>
            <strong>Export validation failed</strong> with{' '}
            {result.errors.length} error{result.errors.length === 1 ? '' : 's'}.
            Select an error to jump to the field:
          </p>
          <ul className="error-list">
            {result.errors.map((e, i) => {
              const { code, detail } = parseExportError(e);
              const label = manifest.fields.find((f) => f.key === detail)?.label ?? detail;
              return (
                <li key={i}>
                  <button
                    type="button"
                    className="btn btn-link error-link"
                    onClick={() => onSelectErrorField(detail)}
                    title={detail ? `Go to field: ${label}` : 'No field attached'}
                  >
                    <code>{code}</code>
                    {detail && (
                      <span>
                        {' → '}
                        {label}
                      </span>
                    )}
                  </button>
                  <span className="visually-hidden">Full error: {e}</span>
                </li>
              );
            })}
          </ul>
        </div>
      )}

      {succeeded && result.licenseRecord && (
        <LicenseRecordView
          license={result.licenseRecord}
          html={result.html as string}
          onSave={() => void handleSave(result.html as string)}
          saveBusy={saveBusy}
          savedPath={savedPath}
          saveError={saveError}
        />
      )}

      {succeeded && !result.licenseRecord && (
        <p role="alert" className="alert alert-error">
          Export succeeded but the backend returned no license record.
        </p>
      )}
    </section>
  );
}

interface LicenseRecordViewProps {
  license: LicenseRecord;
  html: string;
  onSave: () => void;
  saveBusy: boolean;
  savedPath: string | null;
  saveError: string | null;
}

function LicenseRecordView({
  license,
  html,
  onSave,
  saveBusy,
  savedPath,
  saveError,
}: LicenseRecordViewProps) {
  return (
    <div className="license-record">
      <h3>Export ready</h3>
      <dl className="license-grid">
        <div>
          <dt>Template</dt>
          <dd>
            <code>{license.templateId}</code> v{license.templateVersion}
          </dd>
        </div>
        <div>
          <dt>Manifest version</dt>
          <dd>
            <code>{license.manifestVersion}</code>
          </dd>
        </div>
        <div>
          <dt>Format</dt>
          <dd>
            <code>{license.format}</code>
          </dd>
        </div>
        <div>
          <dt>Exported at</dt>
          <dd>{license.exportedAt}</dd>
        </div>
        <div className="license-hash">
          <dt>Content hash (sha256)</dt>
          <dd>
            <code className="hash">{license.contentHash}</code>
          </dd>
        </div>
        <div>
          <dt>Size</dt>
          <dd>{html.length.toLocaleString()} bytes</dd>
        </div>
      </dl>
      <div className="export-save-row">
        <button
          type="button"
          className="btn btn-primary"
          disabled={saveBusy}
          onClick={onSave}
        >
          {saveBusy ? 'Saving…' : 'Save file'}
        </button>
        {savedPath && (
          <p role="status" className="alert alert-success inline">
            Saved to <code>{savedPath}</code>
          </p>
        )}
        {saveError && (
          <p role="alert" className="alert alert-error inline">
            <code>{saveError}</code>
          </p>
        )}
      </div>
    </div>
  );
}
