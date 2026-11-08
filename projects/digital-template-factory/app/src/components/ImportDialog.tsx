import { useEffect, useRef, useState } from 'react';
import { api, errorText } from '../api';

interface ImportDialogProps {
  onClose: () => void;
  onImported: () => void;
}

/**
 * Modal dialog for importing a template from pasted bundle JSON.
 * Backend failures are shown verbatim (error codes included).
 */
export function ImportDialog({ onClose, onImported }: ImportDialogProps) {
  const [bundleJson, setBundleJson] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    textareaRef.current?.focus();
  }, []);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose();
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  async function handleImport() {
    setBusy(true);
    setError(null);
    setSuccess(null);
    try {
      const summary = await api.importTemplate(bundleJson);
      setSuccess(
        `Imported “${summary.name}” (v${summary.version}, ${summary.fieldCount} fields).`,
      );
      onImported();
    } catch (err) {
      // Shown verbatim: includes backend error codes such as
      // TEMPLATE_INVALID or TEMPLATE_VERSION_UNSUPPORTED.
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      className="modal-backdrop"
      role="dialog"
      aria-modal="true"
      aria-labelledby="import-heading"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="modal">
        <h2 id="import-heading">Import template</h2>
        <p className="muted">
          Paste a template bundle JSON document. It is validated by the
          backend before anything is stored.
        </p>
        <label htmlFor="import-json" className="field-label">
          Bundle JSON
        </label>
        <textarea
          id="import-json"
          ref={textareaRef}
          className="textarea"
          rows={10}
          value={bundleJson}
          onChange={(e) => setBundleJson(e.target.value)}
          placeholder='{"manifestVersion": "1.0.0", "templateId": "…", …}'
          spellCheck={false}
        />
        {error && (
          <p role="alert" className="alert alert-error">
            Import failed: <code>{error}</code>
          </p>
        )}
        {success && (
          <p role="status" className="alert alert-success">
            {success}
          </p>
        )}
        <div className="modal-actions">
          <button
            type="button"
            className="btn btn-secondary"
            onClick={onClose}
            disabled={busy}
          >
            Close
          </button>
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => void handleImport()}
            disabled={busy || bundleJson.trim().length === 0}
          >
            {busy ? 'Importing…' : 'Import'}
          </button>
        </div>
      </div>
    </div>
  );
}
