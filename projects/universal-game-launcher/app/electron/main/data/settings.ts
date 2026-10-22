/** Simple key-value settings stored in SQLite. */
import type { DatabaseSync } from 'node:sqlite';
import type { Settings } from '../../../shared/types';

const DEFAULTS: Settings = {
  trackingEnabled: true,
  minimizeOnLaunch: false,
  theme: 'dark',
};

export function getSettings(db: DatabaseSync): Settings {
  const rows = db.prepare('SELECT key, value FROM settings').all() as {
    key: string;
    value: string;
  }[];
  const stored: Record<string, unknown> = {};
  for (const r of rows) {
    try {
      stored[r.key] = JSON.parse(r.value);
    } catch {
      // Corrupt value: fall back to default for this key.
    }
  }
  return {
    trackingEnabled:
      typeof stored.trackingEnabled === 'boolean'
        ? stored.trackingEnabled
        : DEFAULTS.trackingEnabled,
    minimizeOnLaunch:
      typeof stored.minimizeOnLaunch === 'boolean'
        ? stored.minimizeOnLaunch
        : DEFAULTS.minimizeOnLaunch,
    theme:
      stored.theme === 'dark' || stored.theme === 'light' || stored.theme === 'system'
        ? stored.theme
        : DEFAULTS.theme,
  };
}

export function updateSettings(db: DatabaseSync, patch: Partial<Settings>): Settings {
  const set = db.prepare('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)');
  for (const [key, value] of Object.entries(patch)) {
    if (value === undefined) continue;
    set.run(key, JSON.stringify(value));
  }
  return getSettings(db);
}
