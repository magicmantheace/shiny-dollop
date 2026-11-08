import { useCallback, useEffect, useRef, useState } from 'react';
import type { Workflow } from '../../shared/types';
import { dabErrorMessage, getDab } from '../lib/dab';
import { ConfirmDialog, ErrorBanner, formatDateTime } from './ui';

interface Props {
  onOpen: (workflowId: string) => void;
  onRun: (workflowId: string) => void;
}

export function WorkflowsList({ onOpen, onRun }: Props) {
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState('');
  const [newRoot, setNewRoot] = useState('');
  const [deleteTarget, setDeleteTarget] = useState<Workflow | null>(null);
  const [importOpen, setImportOpen] = useState(false);
  const [importText, setImportText] = useState('');
  const [importError, setImportError] = useState('');
  const [importing, setImporting] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      setWorkflows(await getDab().workflowsList());
    } catch (e) {
      setError(dabErrorMessage(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function handleCreate() {
    setError('');
    try {
      const wf = await getDab().workflowsCreate(
        newName.trim() || 'Untitled workflow',
        newRoot.trim(),
      );
      setCreating(false);
      setNewName('');
      setNewRoot('');
      onOpen(wf.id);
    } catch (e) {
      setError(dabErrorMessage(e));
    }
  }

  async function handleDelete() {
    if (!deleteTarget) return;
    setError('');
    try {
      await getDab().workflowsDelete(deleteTarget.id);
      setDeleteTarget(null);
      await refresh();
    } catch (e) {
      setError(dabErrorMessage(e));
    }
  }

  async function handleExport(wf: Workflow) {
    setError('');
    try {
      const json = await getDab().workflowsExport(wf.id);
      const blob = new Blob([json], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${wf.name.replace(/[^\w-]+/g, '_') || 'workflow'}.dab-workflow.json`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) {
      setError(dabErrorMessage(e));
    }
  }

  async function handleImportFile(file: File | undefined) {
    if (!file) return;
    setImportError('');
    try {
      setImportText(await file.text());
    } catch (e) {
      setImportError(dabErrorMessage(e));
    }
  }

  async function handleImportSubmit() {
    const text = importText.trim();
    if (!text) {
      setImportError('Paste workflow JSON or choose a file first.');
      return;
    }
    setImporting(true);
    setImportError('');
    try {
      const wf = await getDab().workflowsImport(text);
      setImportOpen(false);
      setImportText('');
      await refresh();
      onOpen(wf.id);
    } catch (e) {
      setImportError(dabErrorMessage(e));
    } finally {
      setImporting(false);
    }
  }

  return (
    <section aria-labelledby="workflows-heading">
      <div className="section-head">
        <h2 id="workflows-heading">Workflows</h2>
        <div className="section-actions">
          <button type="button" onClick={() => setCreating((v) => !v)}>
            {creating ? 'Close' : 'New workflow'}
          </button>
          <button type="button" onClick={() => setImportOpen(true)}>
            Import
          </button>
        </div>
      </div>

      <ErrorBanner message={error} onDismiss={() => setError('')} />

      {creating && (
        <form
          className="panel"
          onSubmit={(e) => {
            e.preventDefault();
            void handleCreate();
          }}
        >
          <h3>New workflow</h3>
          <label>
            Name
            <input
              type="text"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="e.g. Weekly report backup"
            />
          </label>
          <label>
            Sandbox root
            <input
              type="text"
              value={newRoot}
              onChange={(e) => setNewRoot(e.target.value)}
              placeholder="Folder all workflow paths are relative to"
            />
          </label>
          <div className="form-actions">
            <button type="submit" className="primary">
              Create and edit
            </button>
          </div>
        </form>
      )}

      {loading ? (
        <p>Loading workflows…</p>
      ) : workflows.length === 0 ? (
        <p className="muted">
          No workflows yet. Create one to get started.
        </p>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th scope="col">Name</th>
              <th scope="col">Version</th>
              <th scope="col">Steps</th>
              <th scope="col">Updated</th>
              <th scope="col">Actions</th>
            </tr>
          </thead>
          <tbody>
            {workflows.map((wf) => (
              <tr key={wf.id}>
                <td>{wf.name}</td>
                <td>v{wf.version}</td>
                <td>{wf.steps.length}</td>
                <td>{formatDateTime(wf.updatedAt)}</td>
                <td className="row-actions">
                  <button type="button" onClick={() => onOpen(wf.id)}>
                    Open
                  </button>
                  <button type="button" onClick={() => onRun(wf.id)}>
                    Run
                  </button>
                  <button type="button" onClick={() => void handleExport(wf)}>
                    Export
                  </button>
                  <button
                    type="button"
                    className="danger-text"
                    onClick={() => setDeleteTarget(wf)}
                  >
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {deleteTarget && (
        <ConfirmDialog
          title={`Delete workflow "${deleteTarget.name}"?`}
          body={
            <p>
              This permanently deletes the workflow and its version history.
              It cannot be undone.
            </p>
          }
          confirmLabel="Delete workflow"
          danger
          onConfirm={() => void handleDelete()}
          onCancel={() => setDeleteTarget(null)}
        />
      )}

      {importOpen && (
        <div className="modal-overlay" onClick={() => setImportOpen(false)}>
          <div
            className="modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="import-title"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 id="import-title">Import workflow</h2>
            <p className="muted">
              Paste exported workflow JSON below, or choose a file. Imported
              workflows are validated before anything is saved.
            </p>
            <input
              ref={fileInputRef}
              type="file"
              accept="application/json,.json"
              className="visually-hidden"
              aria-label="Choose workflow JSON file"
              onChange={(e) => void handleImportFile(e.target.files?.[0])}
            />
            <div className="modal-actions modal-actions-start">
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
              >
                Choose file…
              </button>
            </div>
            <label>
              Paste workflow JSON
              <textarea
                rows={8}
                value={importText}
                onChange={(e) => setImportText(e.target.value)}
                placeholder='{"name": "…", "steps": [ … ]}'
              />
            </label>
            {importError && (
              <div className="error-banner" role="alert">
                {importError}
              </div>
            )}
            <div className="modal-actions">
              <button type="button" onClick={() => setImportOpen(false)}>
                Cancel
              </button>
              <button
                type="button"
                className="primary"
                disabled={importing}
                onClick={() => void handleImportSubmit()}
              >
                {importing ? 'Importing…' : 'Import workflow'}
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
