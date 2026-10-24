import { useEffect, useState } from 'react';
import { api, errorText } from '../api';
import {
  loadRecentDocs,
  removeRecentDoc,
  type RecentDoc,
} from '../recentDocs';

interface DocumentsListProps {
  onOpenDocument: (docId: string) => void;
}

/**
 * Recent documents, tracked in a renderer-local localStorage index (the
 * backend exposes no documents:list endpoint). Each entry shows the
 * template name, last-updated date, and a delete action with inline
 * confirmation.
 */
export function DocumentsList({ onOpenDocument }: DocumentsListProps) {
  const [docs, setDocs] = useState<RecentDoc[]>([]);
  const [confirmId, setConfirmId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  useEffect(() => {
    setDocs(loadRecentDocs());
  }, []);

  async function handleDelete(id: string) {
    setDeletingId(id);
    setError(null);
    try {
      await api.deleteDocument(id);
    } catch (err) {
      setError(`Could not delete document: ${errorText(err)}`);
      setDeletingId(null);
      setConfirmId(null);
      return;
    }
    removeRecentDoc(id);
    setDocs(loadRecentDocs());
    setDeletingId(null);
    setConfirmId(null);
  }

  function formatDate(iso: string): string {
    const d = new Date(iso);
    return Number.isNaN(d.getTime()) ? iso : d.toLocaleString();
  }

  return (
    <section aria-labelledby="docs-heading" className="docs-list">
      <h2 id="docs-heading">My documents</h2>

      {error && (
        <p role="alert" className="alert alert-error">
          <code>{error}</code>
        </p>
      )}

      {docs.length === 0 && (
        <p className="muted">
          No documents yet. Pick a template in the gallery to create one.
        </p>
      )}

      <ul className="doc-rows">
        {docs.map((d) => (
          <li key={d.id} className="doc-row">
            <div className="doc-row-main">
              <button
                type="button"
                className="btn btn-link doc-open"
                onClick={() => onOpenDocument(d.id)}
                title={`Open document ${d.id}`}
              >
                {d.templateName}
              </button>
              <span className="muted doc-meta">
                Updated {formatDate(d.updatedAt)}
              </span>
            </div>
            {confirmId === d.id ? (
              <div className="doc-confirm" role="group" aria-label={`Confirm delete of ${d.templateName}`}>
                <span className="muted">Delete this document?</span>
                <button
                  type="button"
                  className="btn btn-danger btn-sm"
                  disabled={deletingId === d.id}
                  onClick={() => void handleDelete(d.id)}
                >
                  {deletingId === d.id ? 'Deleting…' : 'Confirm delete'}
                </button>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  disabled={deletingId === d.id}
                  onClick={() => setConfirmId(null)}
                >
                  Cancel
                </button>
              </div>
            ) : (
              <button
                type="button"
                className="btn btn-danger btn-sm"
                onClick={() => setConfirmId(d.id)}
                aria-label={`Delete document ${d.templateName}`}
              >
                Delete
              </button>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
