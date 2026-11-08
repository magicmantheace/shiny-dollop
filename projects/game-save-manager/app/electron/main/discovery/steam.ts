/**
 * Steam discovery — READ-ONLY. Parses libraryfolders.vdf and
 * steamapps/appmanifest_<appid>.acf to find installed games.
 * Never writes to the Steam installation.
 */
import fs from 'node:fs';
import path from 'node:path';

export interface SteamGame {
  appId: string;
  name: string;
  installDir: string;
  /** Absolute path of the library's steamapps folder this came from. */
  librarySteamAppsDir: string;
}

type VdfValue = string | { [key: string]: VdfValue };

/**
 * Minimal Valve Data Format parser: quoted strings, quoted keys, and
 * brace-delimited objects. Sufficient for libraryfolders.vdf and .acf files.
 */
export function parseVdf(text: string): { [key: string]: VdfValue } {
  let i = 0;
  const n = text.length;

  function skipWhitespace(): void {
    while (i < n && /\s/.test(text[i] as string)) i++;
  }

  function readQuoted(): string {
    // Assumes text[i] === '"'.
    i++; // opening quote
    let out = '';
    while (i < n) {
      const c = text[i] as string;
      if (c === '"') {
        i++;
        return out;
      }
      if (c === '\\' && i + 1 < n) {
        const next = text[i + 1] as string;
        // VDF escapes: \" and \\ (and \n rarely). Keep it simple and honest.
        if (next === '"' || next === '\\') {
          out += next;
          i += 2;
          continue;
        }
      }
      out += c;
      i++;
    }
    throw new Error('Unterminated quoted string in VDF');
  }

  function readValue(): VdfValue {
    skipWhitespace();
    const c = text[i];
    if (c === '{') {
      i++;
      const obj: { [key: string]: VdfValue } = {};
      for (;;) {
        skipWhitespace();
        if (i >= n) throw new Error('Unterminated object in VDF');
        if (text[i] === '}') {
          i++;
          return obj;
        }
        const key = readQuoted();
        obj[key] = readValue();
      }
    }
    if (c === '"') return readQuoted();
    throw new Error(`Unexpected character in VDF: ${c}`);
  }

  const root: { [key: string]: VdfValue } = {};
  for (;;) {
    skipWhitespace();
    if (i >= n) break;
    const key = readQuoted();
    root[key] = readValue();
  }
  return root;
}

/** Default Steam install locations on Windows. Override in tests. */
export function defaultSteamInstallDirs(): string[] {
  if (process.platform !== 'win32') return [];
  const programFiles = process.env['ProgramFiles'] ?? 'C:\\Program Files';
  const programFilesX86 = process.env['ProgramFiles(x86)'] ?? 'C:\\Program Files (x86)';
  return [path.join(programFilesX86, 'Steam'), path.join(programFiles, 'Steam')];
}

function readTextFileIfExists(p: string): string | null {
  try {
    return fs.readFileSync(p, 'utf8');
  } catch {
    return null;
  }
}

/**
 * All Steam library folders: the install dir itself plus every "path" entry
 * in libraryfolders.vdf. Missing/unreadable VDF -> just the install dir.
 */
export function findSteamLibraries(steamInstallDir: string): string[] {
  const libraries = [steamInstallDir];
  const vdfPath = path.join(steamInstallDir, 'steamapps', 'libraryfolders.vdf');
  const raw = readTextFileIfExists(vdfPath);
  if (!raw) return libraries;
  let parsed: { [key: string]: VdfValue };
  try {
    parsed = parseVdf(raw);
  } catch {
    return libraries;
  }
  const folders = parsed['libraryfolders'];
  if (typeof folders !== 'object' || folders === null) return libraries;
  for (const key of Object.keys(folders)) {
    const entry = (folders as { [k: string]: VdfValue })[key];
    if (typeof entry === 'object' && entry !== null) {
      const p = (entry as { [k: string]: VdfValue })['path'];
      if (typeof p === 'string' && p.length > 0 && !libraries.includes(p)) {
        libraries.push(p);
      }
    }
  }
  return libraries;
}

/** Read every appmanifest_*.acf in a library's steamapps folder. */
export function readAppManifests(libraryDir: string): SteamGame[] {
  const steamAppsDir = path.join(libraryDir, 'steamapps');
  let entries: string[];
  try {
    entries = fs.readdirSync(steamAppsDir);
  } catch {
    return [];
  }
  const games: SteamGame[] = [];
  for (const entry of entries) {
    const m = /^appmanifest_(\d+)\.acf$/i.exec(entry);
    if (!m) continue;
    const raw = readTextFileIfExists(path.join(steamAppsDir, entry));
    if (!raw) continue;
    let parsed: { [key: string]: VdfValue };
    try {
      parsed = parseVdf(raw);
    } catch {
      continue; // Corrupt manifest: skip, don't crash discovery.
    }
    const state = parsed['AppState'];
    if (typeof state !== 'object' || state === null) continue;
    const s = state as { [k: string]: VdfValue };
    const appId = typeof s['appid'] === 'string' ? (s['appid'] as string) : (m[1] as string);
    const name = typeof s['name'] === 'string' ? (s['name'] as string) : '';
    const installDir = typeof s['installdir'] === 'string' ? (s['installdir'] as string) : '';
    if (!name || !installDir) continue;
    games.push({ appId, name, installDir, librarySteamAppsDir: steamAppsDir });
  }
  return games;
}

/** Full Steam scan: every install dir -> every library -> every manifest. */
export function discoverSteamGames(steamInstallDirs?: string[]): SteamGame[] {
  const dirs = steamInstallDirs ?? defaultSteamInstallDirs();
  const games: SteamGame[] = [];
  const seenAppIds = new Set<string>();
  for (const installDir of dirs) {
    if (!fs.existsSync(installDir)) continue;
    for (const library of findSteamLibraries(installDir)) {
      for (const game of readAppManifests(library)) {
        if (seenAppIds.has(game.appId)) continue;
        seenAppIds.add(game.appId);
        games.push(game);
      }
    }
  }
  return games;
}
