/**
 * Discovery entry point. Runs the Steam + Epic scans (read-only) and the
 * Battle.net client detection, then derives save-folder candidates from real
 * local evidence. All filesystem roots are injectable for tests; on a real
 * Windows machine the platform defaults are used.
 *
 * Battle.net games are NOT auto-listed — the client has no honest local
 * registry, so those are manual registrations only.
 */
import type { SaveCandidate } from '../../../shared/types';
import { discoverSteamGames, defaultSteamInstallDirs } from './steam';
import { discoverEpicGames, defaultEpicManifestsDir } from './epic';
import { detectBattleNet, defaultBattleNetLauncherPaths, type BattleNetStatus } from './battlenet';
import { discoverSaveCandidates, toInstalledGames } from './candidates';

export interface DiscoveryOptions {
  steamInstallDirs?: string[];
  epicManifestsDir?: string | null;
  battleNetLauncherPaths?: string[];
  /** e.g. C:\Users\Adam. Defaults to the current user's home dir. */
  userProfileDir?: string;
}

export interface DiscoveryResult {
  candidates: SaveCandidate[];
  steamGamesFound: number;
  epicGamesFound: number;
  battleNet: BattleNetStatus;
}

function defaultUserProfileDir(): string {
  // On Windows this is %USERPROFILE%; elsewhere os.homedir() is the honest
  // equivalent (tests always inject an explicit fixture dir).
  const winProfile = process.env['USERPROFILE'];
  if (process.platform === 'win32' && winProfile) return winProfile;
  return process.env['HOME'] ?? process.env['USERPROFILE'] ?? '';
}

export function runDiscovery(options: DiscoveryOptions = {}): DiscoveryResult {
  const steamInstallDirs = options.steamInstallDirs ?? defaultSteamInstallDirs();
  const epicManifestsDir =
    options.epicManifestsDir !== undefined ? options.epicManifestsDir : defaultEpicManifestsDir();
  const battleNetLauncherPaths = options.battleNetLauncherPaths ?? defaultBattleNetLauncherPaths();
  const userProfileDir = options.userProfileDir ?? defaultUserProfileDir();

  const steamGames = discoverSteamGames(steamInstallDirs);
  const epicGames = discoverEpicGames(epicManifestsDir);
  const battleNet = detectBattleNet(battleNetLauncherPaths);

  const candidates = userProfileDir
    ? discoverSaveCandidates({
        games: toInstalledGames(steamGames, epicGames, steamInstallDirs),
        userProfileDir,
      })
    : [];

  return {
    candidates,
    steamGamesFound: steamGames.length,
    epicGamesFound: epicGames.length,
    battleNet,
  };
}

export { discoverSteamGames } from './steam';
export { discoverEpicGames } from './epic';
export { detectBattleNet } from './battlenet';
export { discoverSaveCandidates, toInstalledGames } from './candidates';
