import { useCallback, useEffect, useRef, useState } from 'react';
import type { DocumentRecord, TemplateManifest, TokenUpdate } from '../../shared/types';
import { api, errorText } from '../api';
import { upsertRecentDoc } from '../recentDocs';
import { FieldEditor } from './FieldEditor';
import { TokenEditor } from './TokenEditor';
import { PreviewPane } from './PreviewPane';
import { ExportPanel } from './ExportPanel';

interface EditorProps {
  docId: string;
  onBack: () => void;
}

/**
 * Document editor: left panel holds the schema-generated field editor and
 * the design-token editor; the right panel shows the live (approximate)
 * preview; the export panel sits below.
 */
export function Editor({ docId, onBack }: EditorProps) {
  const [manifest, setManifest] = useState<TemplateManifest | null>(null);
  const [doc, setDoc] = useState<DocumentRecord | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [showExport, setShowExport] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoadError(null);
      try {
        const record = await api.getDocument(docId);
        if (cancelled) return;
        const tmpl = await api.getTemplate(record.templateId);
        if (cancelled) return;
        setDoc(record);
        setManifest(tmpl);
        upsertRecentDoc({
          id: record.id,
          templateId: record.templateId,
          templateName: tmpl.name,
          updatedAt: record.updatedAt,
        });
      } catch (err) {
        if (!cancelled) setLoadError(errorText(err));
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [docId]);

  const applyRecord = useCallback(
    (record: DocumentRecord, tmpl: TemplateManifest) => {
      setDoc(record);
      upsertRecentDoc({
        id: record.id,
        templateId: record.templateId,
        templateName: tmpl.name,
        updatedAt: record.updatedAt,
      });
    },
    [],
  );

  async function handleFieldChange(key: string, value: unknown) {
    if (!doc || !manifest) return;
    // Optimistic local update so typing stays responsive.
    setDoc({ ...doc, data: { ...doc.data, [key]: value } });
    setSaving(true);
    setSaveError(null);
    try {
      const record = await api.updateField(doc.id, key, value);
      applyRecord(record, manifest);
    } catch (err) {
      setSaveError(`Could not save “${key}”: ${errorText(err)}`);
    } finally {
      setSaving(false);
    }
  }

  async function handleTokens(partial: TokenUpdate) {
    if (!doc || !manifest) return;
    setSaving(true);
    setSaveError(null);
    try {
      const record = await api.updateTokens(doc.id, partial);
      applyRecord(record, manifest);
    } catch (err) {
      setSaveError(`Could not save design tokens: ${errorText(err)}`);
    } finally {
      setSaving(false);
    }
  }

  /** Focus the field editor for a manifest field key (used by export errors). */
  function focusField(key: string) {
    const root = rootRef.current;
    if (!root) return;
    const container = root.querySelector(`[data-field-key="${CSS.escape(key)}"]`);
    const target =
      container?.querySelector<HTMLElement>('input, select, textarea, button') ??
      null;
    if (target) {
      target.scrollIntoView({ block: 'center', behavior: 'smooth' });
      target.focus({ preventScroll: true });
    }
  }

  if (loadError) {
    return (
      <section className="editor">
        <button type="button" className="btn btn-secondary" onClick={onBack}>
          ← Back
        </button>
        <p role="alert" className="alert alert-error">
          Could not open document: <code>{loadError}</code>
        </p>
      </section>
    );
  }

  if (!manifest || !doc) {
    return (
      <section className="editor">
        <button type="button" className="btn btn-secondary" onClick={onBack}>
          ← Back
        </button>
        <p className="muted">Loading document…</p>
      </section>
    );
  }

  return (
    <div className="editor" ref={rootRef}>
      <header className="editor-head">
        <button type="button" className="btn btn-secondary" onClick={onBack}>
          ← Back
        </button>
        <div className="editor-title">
          <h2>
            {manifest.name} <span className="muted">v{manifest.version}</span>
          </h2>
          <p className="muted editor-status" role="status">
            {saving ? 'Saving…' : `Last saved ${new Date(doc.updatedAt).toLocaleString()}`}
          </p>
        </div>
        <button
          type="button"
          className="btn btn-primary"
          onClick={() => setShowExport((v) => !v)}
          aria-expanded={showExport}
        >
          {showExport ? 'Hide export' : 'Export'}
        </button>
      </header>

      {saveError && (
        <p role="alert" className="alert alert-error">
          <code>{saveError}</code>
        </p>
      )}

      <div className="editor-layout">
        <div className="editor-left">
          <section aria-labelledby="fields-heading" className="panel">
            <h3 id="fields-heading">Content</h3>
            <FieldEditor
              fields={manifest.fields}
              data={doc.data}
              onFieldChange={(k, v) => void handleFieldChange(k, v)}
            />
          </section>
          <section aria-labelledby="tokens-heading" className="panel">
            <h3 id="tokens-heading" className="visually-hidden">
              Design tokens
            </h3>
            <TokenEditor
              tokens={doc.tokens}
              onApply={(p) => void handleTokens(p)}
            />
          </section>
        </div>
        <div className="editor-right">
          <PreviewPane manifest={manifest} doc={doc} />
        </div>
      </div>

      {showExport && (
        <ExportPanel
          docId={doc.id}
          manifest={manifest}
          onSelectErrorField={focusField}
        />
      )}
    </div>
  );
}
