import { useCallback, useEffect, useState } from 'react';
import type { Site, ThemeInfo } from '../../shared/types';
import { BUSINESS_TYPE_LABELS } from '../labels';
import { getApi } from '../api';
import { ProfileEditor } from './ProfileEditor';
import { ThemePicker } from './ThemePicker';
import { Preview } from './Preview';
import { ExportPanel } from './ExportPanel';

interface SiteWorkspaceProps {
  siteId: string;
  onBack: () => void;
}

type Tab = 'profile' | 'theme' | 'preview' | 'export';

const TABS: { id: Tab; label: string }[] = [
  { id: 'profile', label: 'Profile' },
  { id: 'theme', label: 'Theme' },
  { id: 'preview', label: 'Preview' },
  { id: 'export', label: 'Export' },
];

/**
 * Editor view for one site: Profile / Theme / Preview / Export tabs.
 * Export issues can link back into profile sections via `focusSectionId`.
 */
export function SiteWorkspace({ siteId, onBack }: SiteWorkspaceProps) {
  const [site, setSite] = useState<Site | null>(null);
  const [themes, setThemes] = useState<ThemeInfo[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>('profile');
  const [focusSectionId, setFocusSectionId] = useState<string | null>(null);
  const [previewKey, setPreviewKey] = useState(0);

  useEffect(() => {
    Promise.all([getApi().sites.get(siteId), getApi().themes.list()])
      .then(([loaded, themeList]) => {
        if (!loaded) throw new Error('Site not found. It may have been deleted.');
        setSite(loaded);
        setThemes(themeList);
      })
      .catch((e) => setError(e instanceof Error ? e.message : 'Could not load the site.'));
  }, [siteId]);

  const jumpToSection = useCallback((sectionId: string) => {
    setTab('profile');
    setFocusSectionId(sectionId);
  }, []);

  const handleFocusSectionDone = useCallback(() => setFocusSectionId(null), []);

  if (error) {
    return (
      <div>
        <button type="button" className="button" onClick={onBack}>
          ← Back to sites
        </button>
        <p className="field-error" role="alert">
          {error}
        </p>
      </div>
    );
  }

  if (!site) {
    return (
      <div>
        <button type="button" className="button" onClick={onBack}>
          ← Back to sites
        </button>
        <p className="empty-state">Loading site…</p>
      </div>
    );
  }

  return (
    <div className="workspace">
      <div className="workspace-header">
        <button type="button" className="button" onClick={onBack} aria-label="Back to site list">
          ← Sites
        </button>
        <div>
          <h2>{site.name}</h2>
          <p className="workspace-sub">
            {BUSINESS_TYPE_LABELS[site.businessType]}
          </p>
        </div>
      </div>

      <div className="tab-bar" role="tablist" aria-label="Site editor sections">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            id={`tab-${t.id}`}
            aria-selected={tab === t.id}
            aria-controls={`panel-${t.id}`}
            className={`tab${tab === t.id ? ' tab-active' : ''}`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div
        id={`panel-${tab}`}
        role="tabpanel"
        aria-labelledby={`tab-${tab}`}
        className="tab-panel"
      >
        {tab === 'profile' && (
          <ProfileEditor
            site={site}
            onSaved={setSite}
            focusSectionId={focusSectionId}
            onFocusSectionDone={handleFocusSectionDone}
          />
        )}
        {tab === 'theme' && (
          <ThemePicker
            site={site}
            themes={themes}
            onThemeChanged={(updated) => {
              setSite(updated);
              setPreviewKey((k) => k + 1);
            }}
          />
        )}
        {tab === 'preview' && <Preview siteId={site.id} renderKey={previewKey} />}
        {tab === 'export' && <ExportPanel siteId={site.id} onJumpToSection={jumpToSection} />}
      </div>
    </div>
  );
}
