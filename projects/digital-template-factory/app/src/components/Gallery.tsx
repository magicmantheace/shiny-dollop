import { useCallback, useEffect, useState } from 'react';
import type { TemplateSummary } from '../../shared/types';
import { api, errorText } from '../api';
import { ImportDialog } from './ImportDialog';

interface GalleryProps {
  onOpenDocument: (docId: string) => void;
}

/**
 * Template gallery: one card per available template, each with a
 * "New document" action, plus an "Import template" action that accepts a
 * pasted template-bundle JSON.
 */
export function Gallery({ onOpenDocument }: GalleryProps) {
  const [templates, setTemplates] = useState<TemplateSummary[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [creatingId, setCreatingId] = useState<string | null>(null);
  const [createError, setCreateError] = useState<string | null>(null);
  const [importOpen, setImportOpen] = useState(false);

  const refresh = useCallback(async () => {
    setLoadError(null);
    try {
      setTemplates(await api.listTemplates());
    } catch (err) {
      setTemplates([]);
      setLoadError(errorText(err));
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function handleNewDocument(templateId: string) {
    setCreatingId(templateId);
    setCreateError(null);
    try {
      const doc = await api.createDocument(templateId);
      onOpenDocument(doc.id);
    } catch (err) {
      setCreateError(errorText(err));
    } finally {
      setCreatingId(null);
    }
  }

  return (
    <section aria-labelledby="gallery-heading" className="gallery">
      <div className="gallery-head">
        <h2 id="gallery-heading">Templates</h2>
        <button
          type="button"
          className="btn btn-secondary"
          onClick={() => setImportOpen(true)}
        >
          Import template
        </button>
      </div>

      {loadError && (
        <p role="alert" className="alert alert-error">
          Could not load templates: <code>{loadError}</code>{' '}
          <button type="button" className="btn btn-link" onClick={() => void refresh()}>
            Retry
          </button>
        </p>
      )}
      {createError && (
        <p role="alert" className="alert alert-error">
          Could not create document: <code>{createError}</code>
        </p>
      )}

      {templates === null && <p className="muted">Loading templates…</p>}

      {templates !== null && templates.length === 0 && !loadError && (
        <p className="muted">
          No templates available yet. Import one to get started.
        </p>
      )}

      <ul className="card-grid">
        {templates?.map((t) => (
          <li key={t.templateId} className="card">
            <div className="card-top">
              <h3>{t.name}</h3>
              <span
                className={`badge ${t.source === 'imported' ? 'badge-imported' : 'badge-bundled'}`}
                title={t.source === 'imported' ? 'Imported by the user' : 'Shipped with the app'}
              >
                {t.source}
              </span>
            </div>
            <p className="card-desc">{t.description}</p>
            <dl className="card-meta">
              <div>
                <dt>Version</dt>
                <dd>{t.version}</dd>
              </div>
              <div>
                <dt>Fields</dt>
                <dd>{t.fieldCount}</dd>
              </div>
            </dl>
            <button
              type="button"
              className="btn btn-primary"
              disabled={creatingId !== null}
              onClick={() => void handleNewDocument(t.templateId)}
              aria-label={`New document from ${t.name}`}
            >
              {creatingId === t.templateId ? 'Creating…' : 'New document'}
            </button>
          </li>
        ))}
      </ul>

      {importOpen && (
        <ImportDialog
          onClose={() => setImportOpen(false)}
          onImported={() => {
            setImportOpen(false);
            void refresh();
          }}
        />
      )}
    </section>
  );
}
