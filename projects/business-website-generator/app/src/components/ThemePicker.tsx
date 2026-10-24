import { useState } from 'react';
import type { Site, ThemeInfo } from '../../shared/types';
import { getApi } from '../api';

interface ThemePickerProps {
  site: Site;
  themes: ThemeInfo[];
  onThemeChanged: (site: Site) => void;
}

/**
 * Theme cards. Switching themes calls `sites.setTheme` and reports the
 * updated site upward so the preview tab re-renders.
 */
export function ThemePicker({ site, themes, onThemeChanged }: ThemePickerProps) {
  const [switchingId, setSwitchingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const compatible = themes.filter((t) => t.businessTypes.includes(site.businessType));

  const switchTheme = async (themeId: string) => {
    if (themeId === site.themeId || switchingId) return;
    setSwitchingId(themeId);
    setError(null);
    try {
      const updated = await getApi().sites.setTheme(site.id, themeId);
      onThemeChanged(updated);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not switch theme.');
    } finally {
      setSwitchingId(null);
    }
  };

  if (compatible.length === 0) {
    return <p className="empty-state">No themes are available for this business type yet.</p>;
  }

  return (
    <div>
      {error && (
        <p className="field-error" role="alert">
          {error}
        </p>
      )}
      <ul className="theme-grid" aria-label="Available themes">
        {compatible.map((theme) => {
          const isCurrent = theme.id === site.themeId;
          const isSwitching = switchingId === theme.id;
          return (
            <li key={theme.id} className={`theme-card${isCurrent ? ' theme-current' : ''}`}>
              <h3>{theme.name}</h3>
              <p className="theme-description">{theme.description}</p>
              <p className="theme-pages">
                Pages: {theme.pages.join(', ')}
              </p>
              {isCurrent ? (
                <span className="badge" aria-label="Current theme">
                  Current theme
                </span>
              ) : (
                <button
                  type="button"
                  className="button"
                  disabled={isSwitching}
                  onClick={() => void switchTheme(theme.id)}
                  aria-label={`Use theme ${theme.name}`}
                >
                  {isSwitching ? 'Switching…' : 'Use this theme'}
                </button>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
