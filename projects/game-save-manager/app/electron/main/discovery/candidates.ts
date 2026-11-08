/**
 * Save-folder candidates from REAL local evidence only.
 *
 * For each installed game we search the common Windows save roots for a
 * folder that plausibly holds that game's saves. Every candidate carries an
 * evidence label — the UI must show it so the user can judge trust:
 *
 * - verified-path: the path is attested by local store metadata, e.g. an
 *   existing Steam userdata/<steamid>/<appid>/ folder for a Steam game.
 * - pattern-match: the folder name matches the game title (case-insensitive,
 *   punctuation-insensitive) inside a known save root. A heuristic — the user
 *   confirms before tracking.
 * - manual: registered by the user via the folder picker.
 *
 * Unverifiable locations are NEVER listed. We never invent a save path.
 */
import fs from 'node:fs';
import path from 'node:path';
import type { SaveCandidate, GameSource } from '../../../shared/types';
import type { SteamGame } from './steam';
import type { EpicGame } from './epic';

export interface InstalledGame {
  name: string;
  source: Exclude<GameSource, 'manual'>;
  /** Steam appId — enables the verified-path userdata check. */
  appId?: string;
  /**
   * Steam client install roots (e.g. C:\Program Files (x86)\Steam).
   * Account save data lives under <clientRoot>/userdata — never under a
   * game's library dir, so secondary libraries (e.g. D:\SteamLibrary) must
   * NOT be used to derive the userdata path.
   */
  steamClientRoots?: string[];
}

export interface CandidateSearchInput {
  games: InstalledGame[];
  /** e.g. C:\Users\Adam — parents the well-known save roots. */
  userProfileDir: string;
}

/** Common Windows roots where games keep saves. */
export function saveSearchRoots(userProfileDir: string): string[] {
  return [
    path.join(userProfileDir, 'Documents', 'My Games'),
    path.join(userProfileDir, 'AppData', 'Local'),
    path.join(userProfileDir, 'AppData', 'Roaming'),
    path.join(userProfileDir, 'Saved Games'),
  ];
}

/** Normalize for fuzzy name comparison: lowercase, alphanumeric only. */
export function normalizeName(name: string): string {
  return name.toLowerCase().replace(/[^a-z0-9]/g, '');
}

function listSubdirs(dir: string): string[] {
  let entries: fs.Dirent[];
  try {
    entries = fs.readdirSync(dir, { withFileTypes: true });
  } catch {
    return [];
  }
  return entries.filter((e) => e.isDirectory()).map((e) => path.join(dir, e.name));
}

/**
 * A folder counts as evidence only if it holds at least one file somewhere
 * inside (a few levels deep — e.g. userdata/<id>/<appid>/remote/save.dat).
 */
function dirContainsFiles(dir: string, maxDepth = 3): boolean {
  if (maxDepth < 0) return false;
  let entries: fs.Dirent[];
  try {
    entries = fs.readdirSync(dir, { withFileTypes: true });
  } catch {
    return false;
  }
  for (const e of entries) {
    if (e.isFile()) return true;
    if (e.isDirectory() && dirContainsFiles(path.join(dir, e.name), maxDepth - 1)) return true;
  }
  return false;
}

/**
 * Steam account-save folders: <clientRoot>/userdata/<steamid>/<appid>/.
 * An existing folder here IS the game's save location — verified-path.
 *
 * The userdata tree is searched under each Steam CLIENT root independently
 * of where the game's library lives: a game installed on a secondary library
 * (D:\SteamLibrary) still keeps its account saves under the client's
 * userdata dir, not under the library dir.
 */
function steamUserdataCandidates(game: InstalledGame): SaveCandidate[] {
  const out: SaveCandidate[] = [];
  if (game.source !== 'steam' || !game.appId || !game.steamClientRoots) return out;
  for (const clientRoot of game.steamClientRoots) {
    const userdataDir = path.join(clientRoot, 'userdata');
    let userIds: fs.Dirent[];
    try {
      userIds = fs.readdirSync(userdataDir, { withFileTypes: true });
    } catch {
      continue;
    }
    for (const uid of userIds) {
      if (!uid.isDirectory()) continue;
      const appDir = path.join(userdataDir, uid.name, game.appId);
      try {
        const st = fs.statSync(appDir);
        if (st.isDirectory() && dirContainsFiles(appDir)) {
          out.push({
            gameName: game.name,
            source: game.source,
            savePath: appDir,
            evidence: 'verified-path',
            detail: `Steam userdata folder for app ${game.appId} (account ${uid.name}) — this is where Steam stores this game's saves.`,
          });
        }
      } catch {
        // No folder for this app id under this account — not evidence.
      }
    }
  }
  return out;
}

function patternMatchCandidates(
  game: InstalledGame,
  userProfileDir: string,
): SaveCandidate[] {
  const out: SaveCandidate[] = [];
  const want = normalizeName(game.name);
  if (want.length < 3) return out; // Too short to match honestly.
  for (const root of saveSearchRoots(userProfileDir)) {
    for (const dir of listSubdirs(root)) {
      const base = normalizeName(path.basename(dir));
      if (base.length < 3) continue;
      const matches = base.includes(want) || want.includes(base);
      if (matches && dirContainsFiles(dir)) {
        out.push({
          gameName: game.name,
          source: game.source,
          savePath: dir,
          evidence: 'pattern-match',
          detail: `Folder name "${path.basename(dir)}" resembles "${game.name}" inside ${root}. Confirm it really holds this game's saves before tracking.`,
        });
      }
    }
  }
  return out;
}

/**
 * Find save-folder candidates for installed games.
 * Dedupes case-insensitively (Windows paths are case-insensitive).
 */
export function discoverSaveCandidates(input: CandidateSearchInput): SaveCandidate[] {
  const found: SaveCandidate[] = [];
  const seen = new Set<string>();
  function push(c: SaveCandidate): void {
    const key = c.savePath.toLowerCase();
    if (seen.has(key)) return;
    seen.add(key);
    found.push(c);
  }
  for (const game of input.games) {
    for (const c of steamUserdataCandidates(game)) push(c);
    for (const c of patternMatchCandidates(game, input.userProfileDir)) push(c);
  }
  found.sort((a, b) => a.gameName.localeCompare(b.gameName));
  return found;
}

/** Adapt raw Steam/Epic scan results into the candidate search input. */
export function toInstalledGames(
  steamGames: SteamGame[],
  epicGames: EpicGame[],
  /**
   * Steam client install roots. Userdata is searched here — never under a
   * game's library dir.
   */
  steamInstallDirs: string[] = [],
): InstalledGame[] {
  const games: InstalledGame[] = steamGames.map((g) => ({
    name: g.name,
    source: 'steam' as const,
    appId: g.appId,
    steamClientRoots: steamInstallDirs,
  }));
  for (const g of epicGames) {
    games.push({ name: g.displayName, source: 'epic' as const });
  }
  return games;
}
