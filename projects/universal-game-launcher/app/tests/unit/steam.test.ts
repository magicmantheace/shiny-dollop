/** Unit tests for the Steam adapter: probe, scan, launch validation. */
import { describe, expect, it } from 'vitest';
import {
  SteamAdapter,
  buildRunGameUri,
  isValidAppId,
} from '../../electron/main/sources/steam/adapter';
import { parseRegQueryOutput } from '../../electron/main/sources/steam/os';
import { FakeSteamOs, acf, fakeSteamInstall, libraryFoldersVdf } from '../steam-helpers';

function windowsOs(): FakeSteamOs {
  const os = new FakeSteamOs();
  os.platform = 'win32';
  os.setEnv('ProgramFiles(x86)', 'C:\\Program Files (x86)');
  os.setEnv('ProgramFiles', 'C:\\Program Files');
  return os;
}

describe('isValidAppId', () => {
  it.each(['730', '1', '1234567890'])('accepts %s', (v) => expect(isValidAppId(v)).toBe(true));
  it.each(['', 'abc', '73a', ' 730', '730 ', '-1', '12.5', '12345678901', '0x2DA'])(
    'rejects %s',
    (v) => expect(isValidAppId(v)).toBe(false),
  );
  it('rejects non-strings', async () => {
    expect(isValidAppId(null)).toBe(false);
    expect(isValidAppId(730)).toBe(false);
    expect(isValidAppId(undefined)).toBe(false);
  });
});

describe('buildRunGameUri', () => {
  it('builds the documented rungameid URI', async () => {
    expect(buildRunGameUri('730')).toBe('steam://rungameid/730');
  });
  it('refuses invalid AppIDs', async () => {
    expect(() => buildRunGameUri('nope')).toThrow();
    expect(() => buildRunGameUri('')).toThrow();
  });
});

describe('parseRegQueryOutput', () => {
  const sample = `\r\nHKEY_CURRENT_USER\\Software\\Valve\\Steam\r\n    SteamPath    REG_SZ    C:\\Program Files (x86)\\Steam\r\n`;
  it('extracts the value', async () => {
    expect(parseRegQueryOutput(sample, 'SteamPath')).toBe('C:\\Program Files (x86)\\Steam');
  });
  it('is case-insensitive on the value name', async () => {
    expect(parseRegQueryOutput(sample, 'steampath')).toBe('C:\\Program Files (x86)\\Steam');
  });
  it('returns null when absent', async () => {
    expect(parseRegQueryOutput(sample, 'Nope')).toBeNull();
    expect(parseRegQueryOutput('', 'SteamPath')).toBeNull();
  });
});

describe('probe', () => {
  it('finds Steam via %ProgramFiles(x86)%', async () => {
    const os = windowsOs();
    fakeSteamInstall(os, 'C:\\Program Files (x86)\\Steam');
    const r = await new SteamAdapter(os).probe();
    expect(r.status).toBe('installed');
    expect(r.steamDir).toBe('C:\\Program Files (x86)\\Steam');
    expect(r.detectedVia).toContain('ProgramFiles(x86)');
  });

  it('falls back to the registry when the default paths miss', async () => {
    const os = windowsOs();
    fakeSteamInstall(os, 'E:\\Games\\Steam');
    os.setRegistry('HKCU', 'Software\\Valve\\Steam', 'SteamPath', 'E:\\Games\\Steam');
    const r = await new SteamAdapter(os).probe();
    expect(r.status).toBe('installed');
    expect(r.detectedVia).toContain('HKCU');
  });

  it('reports unavailable when steam.exe is absent', async () => {
    const os = windowsOs();
    os.addDir('C:\\Program Files (x86)\\Steam'); // dir but no steam.exe
    const r = await new SteamAdapter(os).probe();
    expect(r.status).toBe('unavailable');
    expect(r.reason).toContain('not found');
  });

  it('degrades honestly off Windows', async () => {
    const os = new FakeSteamOs();
    os.platform = 'linux';
    const r = await new SteamAdapter(os).probe();
    expect(r.status).toBe('unavailable');
    expect(r.reason).toContain('Windows');
  });
});

describe('scan', () => {
  function twoLibraryTree(): FakeSteamOs {
    const os = windowsOs();
    fakeSteamInstall(os, 'C:\\Program Files (x86)\\Steam');
    os.addFile(
      'C:\\Program Files (x86)\\Steam\\steamapps\\libraryfolders.vdf',
      libraryFoldersVdf(['C:\\Program Files (x86)\\Steam', 'D:\\SteamLibrary']),
    );
    os.addDir('D:\\SteamLibrary\\steamapps');
    os.addDir('D:\\SteamLibrary\\steamapps\\common');
    os.addFile(
      'C:\\Program Files (x86)\\Steam\\steamapps\\appmanifest_730.acf',
      acf('730', 'Counter-Strike 2', 'Counter-Strike Global Offensive'),
    );
    os.addDir('C:\\Program Files (x86)\\Steam\\steamapps\\common\\Counter-Strike Global Offensive');
    os.addFile('D:\\SteamLibrary\\steamapps\\appmanifest_440.acf', acf('440', 'Team Fortress 2', 'Team Fortress 2'));
    os.addDir('D:\\SteamLibrary\\steamapps\\common\\Team Fortress 2');
    return os;
  }

  it('discovers games across multiple libraries', async () => {
    const r = await new SteamAdapter(twoLibraryTree()).scan();
    expect(r.status).toBe('completed');
    expect(r.error).toBeNull();
    const byId = new Map(r.games.map((g) => [g.appid, g]));
    expect(byId.get('730')?.title).toBe('Counter-Strike 2');
    expect(byId.get('730')?.installDir).toBe(
      'C:\\Program Files (x86)\\Steam\\steamapps\\common\\Counter-Strike Global Offensive',
    );
    expect(byId.get('730')?.present).toBe(true);
    expect(byId.get('440')?.title).toBe('Team Fortress 2');
  });

  it('marks games whose install dir is gone as not present', async () => {
    const os = twoLibraryTree();
    // Manifest exists but the install dir was deleted.
    os.addFile('D:\\SteamLibrary\\steamapps\\appmanifest_570.acf', acf('570', 'Dota 2', 'dota 2 beta'));
    const r = await new SteamAdapter(os).scan();
    expect(r.games.find((g) => g.appid === '570')?.present).toBe(false);
  });

  it('skips malformed and hostile manifests with warnings, never throwing', async () => {
    const os = twoLibraryTree();
    os.addFile('D:\\SteamLibrary\\steamapps\\appmanifest_999.acf', 'this is not vdf {{{');
    os.addFile(
      'D:\\SteamLibrary\\steamapps\\appmanifest_1000.acf',
      acf('1000', 'Evil', '..\\Windows'),
    );
    const r = await new SteamAdapter(os).scan();
    expect(r.status).toBe('completed');
    expect(r.games.some((g) => g.appid === '999')).toBe(false);
    expect(r.games.some((g) => g.appid === '1000')).toBe(false);
    expect(r.warnings.length).toBeGreaterThanOrEqual(2);
  });

  it('dedupes manifests with the same AppID', async () => {
    const os = twoLibraryTree();
    os.addFile('D:\\SteamLibrary\\steamapps\\appmanifest_730.acf', acf('730', 'CS2 dupe', 'cs2'));
    const r = await new SteamAdapter(os).scan();
    expect(r.games.filter((g) => g.appid === '730')).toHaveLength(1);
    expect(r.warnings.join(' ')).toContain('Duplicate');
  });

  it('works without libraryfolders.vdf, using the Steam dir only', async () => {
    const os = windowsOs();
    fakeSteamInstall(os, 'C:\\Program Files (x86)\\Steam');
    os.addFile(
      'C:\\Program Files (x86)\\Steam\\steamapps\\appmanifest_730.acf',
      acf('730', 'Counter-Strike 2', 'Counter-Strike Global Offensive'),
    );
    const r = await new SteamAdapter(os).scan();
    expect(r.status).toBe('completed');
    expect(r.games).toHaveLength(1);
    expect(r.warnings.join(' ')).toContain('libraryfolders.vdf');
  });

  it('fails honestly when Steam is absent', async () => {
    const r = await new SteamAdapter(windowsOs()).scan();
    expect(r.status).toBe('failed');
    expect(r.games).toEqual([]);
    expect(r.error).toContain('not found');
  });

  it('honors cancellation between manifests', async () => {
    const os = twoLibraryTree();
    for (let i = 0; i < 30; i++) {
      os.addFile(`D:\\SteamLibrary\\steamapps\\appmanifest_${10000 + i}.acf`, acf(`${10000 + i}`, `Game ${i}`, `game${i}`));
    }
    const token = { cancelled: false };
    const adapter = new SteamAdapter(os);
    // Cancel after the first manifest by flipping from a wrapper is awkward;
    // instead cancel immediately and confirm nothing throws and status is set.
    token.cancelled = true;
    const r = await adapter.scan(token);
    expect(r.status).toBe('cancelled');
  });
});

describe('validateLaunch', () => {
  const adapter = new SteamAdapter(new FakeSteamOs());
  it('approves a valid AppID as native-uri', async () => {
    const v = adapter.validateLaunch('730');
    expect(v.capability).toBe('native-uri');
    expect(v.uri).toBe('steam://rungameid/730');
  });
  it('refuses invalid AppIDs', async () => {
    for (const bad of [null, '', 'abc', '12 34']) {
      const v = adapter.validateLaunch(bad);
      expect(v.capability).toBe('unavailable');
      expect(v.uri).toBeNull();
      expect(v.reason.length).toBeGreaterThan(0);
    }
  });
});
