import { useEffect, useState } from 'react';
import type { SiteSummary, ThemeInfo } from '../../shared/types';
import { BUSINESS_TYPE_LABELS } from '../labels';
import { formatUpdatedAt, getApi } from '../api';
import { Modal } from './Modal';
import { NewSiteWizard } from './NewSiteWizard';

interface SiteListProps {
  onOpen: (id: string) => void;
}

/** Dashboard: site list (name, type, theme, updated) + wizard + delete confirm. */
export function SiteList({ onOpen }: SiteListProps) {
  const [sites, setSites] = useState<SiteSummary[] | null>(null);
  const [themes, setThemes] = useState<ThemeInfo[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [wizardOpen, setWizardOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<SiteSummary | null>(null);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    Promise.all([getApi().sites.list(), getApi().themes.list()])
      .then(([siteList, themeList]) => {
        setSites(siteList);
        setThemes(themeList);
      })
      .catch((e) => setError(e instanceof Error ? e.message : 'Could not load sites.'));
  }, []);

  const themeName = (id: string) => themes.find((t) => t.id === id)?.name ?? id;

  const confirmDelete = async () => {
    if (!deleteTarget || deleting) return;
    setDeleting(true);
    try {
      await getApi().sites.delete(deleteTarget.id);
      setSites((prev) => (prev ?? []).filter((s) => s.id !== deleteTarget.id));
      setDeleteTarget(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not delete the site.');
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div className="dashboard">
      <div className="dashboard-header">
        <h2 id="sites-heading">Your sites</h2>
        <button type="button" className="button button-primary" onClick={() => setWizardOpen(true)}>
          New site
        </button>
      </div>

      {error && (
        <p className="field-error" role="alert">
          {error}
        </p>
      )}

      {!sites && !error && <p className="empty-state">Loading sites…</p>}

      {sites && sites.length === 0 && (
        <p className="empty-state">
          No sites yet. Use “New site” to generate your first business website.
        </p>
      )}

      {sites && sites.length > 0 && (
        <ul className="site-list" aria-labelledby="sites-heading">
          {sites.map((site) => (
            <li key={site.id} className="site-card">
              <div className="site-card-main">
                <h3>{site.name}</h3>
                <dl className="site-meta">
                  <div>
                    <dt>Type</dt>
                    <dd>{BUSINESS_TYPE_LABELS[site.businessType]}</dd>
                  </div>
                  <div>
                    <dt>Theme</dt>
                    <dd>{themeName(site.themeId)}</dd>
                  </div>
                  <div>
                    <dt>Updated</dt>
                    <dd>{formatUpdatedAt(site.updatedAt)}</dd>
                  </div>
                </dl>
              </div>
              <div className="site-card-actions">
                <button type="button" className="button" onClick={() => onOpen(site.id)}>
                  Open
                </button>
                <button
                  type="button"
                  className="button button-danger-ghost"
                  aria-label={`Delete site ${site.name}`}
                  onClick={() => setDeleteTarget(site)}
                >
                  Delete
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}

      {wizardOpen && (
        <NewSiteWizard
          onClose={() => setWizardOpen(false)}
          onCreated={(created) => {
            // Site extends SiteSummary, so it slots straight into the list.
            setSites((prev) => [...(prev ?? []), created]);
            setWizardOpen(false);
            onOpen(created.id);
          }}
        />
      )}

      {deleteTarget && (
        <Modal title="Delete site" onClose={() => setDeleteTarget(null)}>
          <p>
            Delete <strong>{deleteTarget.name}</strong>? This removes the site and its profile
            from this computer. Exported website folders are not affected. This cannot be undone.
          </p>
          <div className="row-actions">
            <button type="button" className="button" onClick={() => setDeleteTarget(null)}>
              Cancel
            </button>
            <button
              type="button"
              className="button button-danger"
              disabled={deleting}
              onClick={() => void confirmDelete()}
              autoFocus
            >
              {deleting ? 'Deleting…' : 'Delete site'}
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}
