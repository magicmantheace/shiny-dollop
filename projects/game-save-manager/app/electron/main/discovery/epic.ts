/**
 * Epic Games discovery — READ-ONLY. Reads the JSON `.item` manifests the
 * Epic Games Launcher keeps under
 * %ProgramData%\Epic\EpicGamesLauncher\Data\Manifests.
 * Never writes to the Epic installation.
 */
import fs from 'node:fs';
import path from 'node:path';

export interface EpicGame {
  displayName: string;
  installLocation: string;
  appName: string;
  catalogItemId: string;
}

interface EpicItemJson {
  DisplayName?: unknown;
  InstallLocation?: unknown;
  AppName?: unknown;
  CatalogItemId?: unknown;
}

/** Default Epic manifests directory on Windows. Override in tests. */
export function defaultEpicManifestsDir(): string | null {
  if (process.platform !== 'win32') return null;
  const programData = process.env['ProgramData'] ?? 'C:\\ProgramData';
  return path.join(programData, 'Epic', 'EpicGamesLauncher', 'Data', 'Manifests');
}

function parseItemFile(filePath: string): EpicGame | null {
  let raw: string;
  try {
    raw = fs.readFileSync(filePath, 'utf8');
  } catch {
    return null;
  }
  let json: EpicItemJson;
  try {
    json = JSON.parse(raw) as EpicItemJson;
  } catch {
    return null; // Corrupt manifest: skip, don't crash discovery.
  }
  const displayName = typeof json.DisplayName === 'string' ? json.DisplayName : '';
  const installLocation = typeof json.InstallLocation === 'string' ? json.InstallLocation : '';
  const appName = typeof json.AppName === 'string' ? json.AppName : '';
  const catalogItemId = typeof json.CatalogItemId === 'string' ? json.CatalogItemId : '';
  if (!displayName || !installLocation) return null;
  return { displayName, installLocation, appName, catalogItemId };
}

/** Read every *.item manifest in the directory. Missing dir -> []. */
export function discoverEpicGames(manifestsDir?: string | null): EpicGame[] {
  const dir = manifestsDir ?? defaultEpicManifestsDir();
  if (!dir) return [];
  let entries: string[];
  try {
    entries = fs.readdirSync(dir);
  } catch {
    return [];
  }
  const games: EpicGame[] = [];
  for (const entry of entries) {
    if (!entry.toLowerCase().endsWith('.item')) continue;
    const game = parseItemFile(path.join(dir, entry));
    if (game) games.push(game);
  }
  games.sort((a, b) => a.displayName.localeCompare(b.displayName));
  return games;
}
