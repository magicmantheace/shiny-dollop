/**
 * Discovery tests against fixture Steam/Epic/Battle.net installations.
 * Save candidates must carry honest evidence labels; unverifiable games
 * must NOT produce candidates.
 */
import { afterEach, describe, expect, it } from 'vitest';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { discoverEpicGames } from '../../electron/main/discovery/epic';
import { detectBattleNet } from '../../electron/main/discovery/battlenet';
import { discoverSteamGames, parseVdf } from '../../electron/main/discovery/steam';
import { discoverSaveCandidates, toInstalledGames } from '../../electron/main/discovery/candidates';
import { runDiscovery } from '../../electron/main/discovery';

let tmpDirs: string[] = [];
afterEach(() => {
  for (const d of tmpDirs) fs.rmSync(d, { recursive: true, force: true });
  tmpDirs = [];
});

function mkTmp(): string {
  const d = fs.mkdtempSync(path.join(os.tmpdir(), 'gsm-discovery-'));
  tmpDirs.push(d);
  return d;
}

function write(p: string, content: string): void {
  fs.mkdirSync(path.dirname(p), { recursive: true });
  fs.writeFileSync(p, content, 'utf8');
}

/** Fixture Steam install with two libraries, two manifests, one userdata dir. */
function fixtureSteam(): { installDir: string } {
  const root = mkTmp();
  const installDir = path.join(root, 'Steam');
  const steamApps = path.join(installDir, 'steamapps');
  const lib2 = path.join(root, 'SteamLibrary');

  write(
    path.join(steamApps, 'libraryfolders.vdf'),
    `"libraryfolders"
{
\t"0"
\t{
\t\t"path"\t\t"${installDir.replace(/\\/g, '\\\\')}"
\t\t"label"\t\t""
\t\t"contentid"\t\t"123"
\t}
\t"1"
\t{
\t\t"path"\t\t"${lib2.replace(/\\/g, '\\\\')}"
\t\t"label"\t\t""
\t}
}`,
  );
  write(
    path.join(steamApps, 'appmanifest_100.acf'),
    `"AppState"
{
\t"appid"\t\t"100"
\t"name"\t\t"Test Valley"
\t"installdir"\t\t"Test Valley"
}`,
  );
  write(
    path.join(lib2, 'steamapps', 'appmanifest_200.acf'),
    `"AppState"
{
\t"appid"\t\t"200"
\t"name"\t\t"Hollow Test"
\t"installdir"\t\t"Hollow Test"
}`,
  );
  // Corrupt manifest: must be skipped, not crash discovery.
  write(path.join(steamApps, 'appmanifest_300.acf'), 'this is not vdf {{{');

  // Steam userdata for app 100 — real save evidence.
  write(path.join(installDir, 'userdata', '76561198000000001', '100', 'remote', 'save1.dat'), 'userdata save');

  return { installDir };
}

function fixtureEpic(): { manifestsDir: string } {
  const root = mkTmp();
  const manifestsDir = path.join(root, 'Manifests');
  write(
    path.join(manifestsDir, 'abc123.item'),
    JSON.stringify({
      DisplayName: 'Epic Test Game',
      InstallLocation: 'C:\\Games\\EpicTestGame',
      AppName: 'EpicTestGame',
      CatalogItemId: 'xyz',
    }),
  );
  write(path.join(manifestsDir, 'broken.item'), '{not json');
  return { manifestsDir };
}

/** Fixture user profile with a My Games folder matching "Test Valley". */
function fixtureProfile(): { profile: string } {
  const root = mkTmp();
  const profile = path.join(root, 'home');
  write(path.join(profile, 'Documents', 'My Games', 'Test Valley', 'Saves', 'save.dat'), 'test valley save');
  write(path.join(profile, 'Documents', 'My Games', 'Unrelated Folder', 'notes.txt'), 'not a game save');
  return { profile };
}

/**
 * Fixture Steam install where the GAME lives on a secondary library but its
 * userdata lives under the CLIENT root (where Steam actually keeps it).
 */
function fixtureSteamSecondaryLibrary(): { installDir: string; libraryDir: string } {
  const root = mkTmp();
  const installDir = path.join(root, 'Client', 'Steam');
  const libraryDir = path.join(root, 'Games', 'SteamLibrary');

  write(
    path.join(installDir, 'steamapps', 'libraryfolders.vdf'),
    `"libraryfolders"
{
\t"0"
\t{
\t\t"path"\t\t"${installDir.replace(/\\/g, '\\\\')}"
\t}
\t"1"
\t{
\t\t"path"\t\t"${libraryDir.replace(/\\/g, '\\\\')}"
\t}
}`,
  );
  // App 200 is installed on the SECONDARY library…
  write(
    path.join(libraryDir, 'steamapps', 'appmanifest_200.acf'),
    `"AppState"
{
\t"appid"\t\t"200"
\t"name"\t\t"Hollow Test"
\t"installdir"\t\t"Hollow Test"
}`,
  );
  // …but its account saves live under the CLIENT root's userdata tree.
  write(
    path.join(installDir, 'userdata', '76561198000000001', '200', 'remote', 'save.dat'),
    'hollow test save',
  );

  return { installDir, libraryDir };
}

describe('parseVdf', () => {
  it('parses nested objects and escaped quotes', () => {
    const parsed = parseVdf(`"root"\n{\n\t"a"\t\t"1"\n\t"child"\n\t{\n\t\t"b"\t\t"va\\"l"\n\t}\n}`);
    expect(parsed['root']).toEqual({ a: '1', child: { b: 'va"l' } });
  });

  it('throws on truncated input', () => {
    expect(() => parseVdf('"root" { "a" "1"')).toThrow();
  });
});

describe('discoverSteamGames', () => {
  it('reads libraryfolders.vdf and every valid appmanifest', () => {
    const { installDir } = fixtureSteam();
    const games = discoverSteamGames([installDir]);
    const names = games.map((g) => g.name).sort();
    expect(names).toEqual(['Hollow Test', 'Test Valley']);
    const valley = games.find((g) => g.appId === '100');
    expect(valley?.installDir).toBe('Test Valley');
  });

  it('returns [] for a missing install dir', () => {
    expect(discoverSteamGames([path.join('nope', 'not-here')])).toEqual([]);
  });
});

describe('discoverEpicGames', () => {
  it('reads .item JSON manifests and skips corrupt ones', () => {
    const { manifestsDir } = fixtureEpic();
    const games = discoverEpicGames(manifestsDir);
    expect(games).toHaveLength(1);
    expect(games[0]?.displayName).toBe('Epic Test Game');
    expect(games[0]?.installLocation).toBe('C:\\Games\\EpicTestGame');
  });

  it('returns [] for a missing manifests dir', () => {
    expect(discoverEpicGames(path.join('nope', 'not-here'))).toEqual([]);
  });
});

describe('detectBattleNet', () => {
  it('detects the launcher when the executable exists', () => {
    const root = mkTmp();
    const launcher = path.join(root, 'Battle.net Launcher.exe');
    write(launcher, '');
    expect(detectBattleNet([launcher])).toEqual({ detected: true, launcherPath: launcher });
  });

  it('reports not detected when nothing exists', () => {
    expect(detectBattleNet([path.join('nope', 'Battle.net Launcher.exe')])).toEqual({
      detected: false,
    });
  });
});

describe('discoverSaveCandidates', () => {
  it('labels Steam userdata folders as verified-path', () => {
    const { installDir } = fixtureSteam();
    const { profile } = fixtureProfile();
    const steamGames = discoverSteamGames([installDir]);
    const candidates = discoverSaveCandidates({
      games: toInstalledGames(steamGames, [], [installDir]),
      userProfileDir: profile,
    });

    const verified = candidates.filter((c) => c.evidence === 'verified-path');
    expect(verified).toHaveLength(1);
    expect(verified[0]?.gameName).toBe('Test Valley');
    expect(verified[0]?.savePath).toContain(path.join('userdata', '76561198000000001', '100'));
    expect(verified[0]?.detail.length).toBeGreaterThan(0);
  });

  it('labels name matches in save roots as pattern-match', () => {
    const { installDir } = fixtureSteam();
    const { profile } = fixtureProfile();
    const steamGames = discoverSteamGames([installDir]);
    const candidates = discoverSaveCandidates({
      games: toInstalledGames(steamGames, [], [installDir]),
      userProfileDir: profile,
    });

    const pattern = candidates.filter((c) => c.evidence === 'pattern-match');
    expect(pattern.some((c) => c.gameName === 'Test Valley')).toBe(true);
    const match = pattern.find((c) => c.gameName === 'Test Valley');
    expect(match?.savePath).toContain(path.join('My Games', 'Test Valley'));
    expect(match?.detail).toMatch(/confirm/i);
  });

  it('never invents candidates for games with no local evidence', () => {
    const { installDir } = fixtureSteam();
    const { profile } = fixtureProfile();
    const steamGames = discoverSteamGames([installDir]);
    const candidates = discoverSaveCandidates({
      games: toInstalledGames(steamGames, [], [installDir]),
      userProfileDir: profile,
    });
    // "Hollow Test" has a manifest but no save folder anywhere.
    expect(candidates.some((c) => c.gameName === 'Hollow Test')).toBe(false);
    // Unrelated folders are not candidates for anything.
    expect(candidates.some((c) => c.savePath.includes('Unrelated Folder'))).toBe(false);
  });

  it('dedupes candidates case-insensitively', () => {
    const { profile } = fixtureProfile();
    const candidates = discoverSaveCandidates({
      games: [
        { name: 'Test Valley', source: 'steam' },
        { name: 'test valley', source: 'steam' },
      ],
      userProfileDir: profile,
    });
    const keys = candidates.map((c) => c.savePath.toLowerCase());
    expect(new Set(keys).size).toBe(keys.length);
  });

  it('finds userdata under the Steam client root for games on secondary libraries', () => {
    const { installDir, libraryDir } = fixtureSteamSecondaryLibrary();
    const { profile } = fixtureProfile();
    const steamGames = discoverSteamGames([installDir]);
    expect(steamGames.map((g) => g.appId)).toEqual(['200']);

    const candidates = discoverSaveCandidates({
      games: toInstalledGames(steamGames, [], [installDir]),
      userProfileDir: profile,
    });

    const verified = candidates.filter((c) => c.evidence === 'verified-path');
    expect(verified).toHaveLength(1);
    expect(verified[0]?.gameName).toBe('Hollow Test');
    // Under the CLIENT root's userdata tree…
    expect(verified[0]?.savePath).toBe(
      path.join(installDir, 'userdata', '76561198000000001', '200'),
    );
    // …never under the secondary library dir (the old code looked there).
    expect(verified[0]?.savePath.startsWith(libraryDir)).toBe(false);
  });
});

describe('runDiscovery', () => {
  it('combines scans and reports counts plus Battle.net status', () => {
    const { installDir } = fixtureSteam();
    const { manifestsDir } = fixtureEpic();
    const { profile } = fixtureProfile();
    const root = mkTmp();
    const launcher = path.join(root, 'Battle.net Launcher.exe');
    write(launcher, '');

    const result = runDiscovery({
      steamInstallDirs: [installDir],
      epicManifestsDir: manifestsDir,
      battleNetLauncherPaths: [launcher],
      userProfileDir: profile,
    });

    expect(result.steamGamesFound).toBe(2);
    expect(result.epicGamesFound).toBe(1);
    expect(result.battleNet.detected).toBe(true);
    expect(result.candidates.length).toBeGreaterThan(0);
    // Every candidate carries an evidence label — the honesty contract.
    for (const c of result.candidates) {
      expect(['verified-path', 'pattern-match', 'manual']).toContain(c.evidence);
      expect(c.detail.length).toBeGreaterThan(0);
    }
  });
});
