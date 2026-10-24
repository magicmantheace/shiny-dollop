/** Unit tests for the Epic adapter: probe, manifest parsing, scan, launch validation. */
import { describe, expect, it } from 'vitest';
import {
  EPIC_LAUNCHER_URI,
  EpicAdapter,
} from '../../electron/main/sources/epic/adapter';
import { parseEpicManifest } from '../../electron/main/sources/epic/manifest';
import { FakeEpicOs, MANIFEST_DIR, fakeEpicInstall, itemManifest } from '../epic-helpers';

function windowsOs(): FakeEpicOs {
  const os = new FakeEpicOs();
  os.platform = 'win32';
  return fakeEpicInstall(os);
}

describe('parseEpicManifest', () => {
  it('parses a well-formed manifest, reading only whitelisted fields', async () => {
    const r = parseEpicManifest(itemManifest(), 'win32');
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.manifest).toMatchObject({
      displayName: 'Fortnite',
      appName: 'Fortnite',
      installLocation: 'C:\\Program Files\\Epic Games\\Fortnite',
      catalogNamespace: 'deadbeef1234',
    });
  });

  it('rejects invalid JSON', async () => {
    const r = parseEpicManifest('{oops', 'win32');
    expect(r.ok).toBe(false);
    if (r.ok) return;
    expect(r.error.code).toBe('INVALID_JSON');
  });

  it('rejects non-object roots', async () => {
    for (const text of ['[1,2]', '"str"', '42', 'null']) {
      const r = parseEpicManifest(text, 'win32');
      expect(r.ok).toBe(false);
    }
  });

  it('rejects missing or empty DisplayName', async () => {
    expect(parseEpicManifest(itemManifest({ DisplayName: '' }), 'win32').ok).toBe(false);
    expect(parseEpicManifest(itemManifest({ DisplayName: 42 }), 'win32').ok).toBe(false);
    const noName = JSON.parse(itemManifest());
    delete noName.DisplayName;
    expect(parseEpicManifest(JSON.stringify(noName), 'win32').ok).toBe(false);
  });

  it('rejects hostile AppName values', async () => {
    for (const appName of ['', 'has space', 'semi;colon', '../escape', 'a'.repeat(129), 42, null]) {
      const r = parseEpicManifest(itemManifest({ AppName: appName }), 'win32');
      expect(r.ok).toBe(false);
    }
  });

  it('rejects relative and traversing InstallLocation values', async () => {
    expect(
      parseEpicManifest(itemManifest({ InstallLocation: 'relative\\path' }), 'win32').ok,
    ).toBe(false);
    expect(
      parseEpicManifest(itemManifest({ InstallLocation: 'C:\\Games\\..\\Windows' }), 'win32').ok,
    ).toBe(false);
    expect(
      parseEpicManifest(itemManifest({ InstallLocation: '' }), 'win32').ok,
    ).toBe(false);
  });

  it('accepts UNC install locations on Windows', async () => {
    const r = parseEpicManifest(
      itemManifest({ InstallLocation: '\\\\SERVER\\Games\\Fortnite' }),
      'win32',
    );
    expect(r.ok).toBe(true);
  });

  it('accepts a missing CatalogNamespace', async () => {
    const raw = JSON.parse(itemManifest());
    delete raw.CatalogNamespace;
    const r = parseEpicManifest(JSON.stringify(raw), 'win32');
    expect(r.ok).toBe(true);
    if (r.ok) expect(r.manifest.catalogNamespace).toBeNull();
  });

  it('warns on unknown fields but still parses', async () => {
    const r = parseEpicManifest(itemManifest({ SomeFutureField: true }), 'win32');
    expect(r.ok).toBe(true);
    if (r.ok) expect(r.warnings.some((w) => w.includes('SomeFutureField'))).toBe(true);
  });
});

describe('probe', () => {
  it('finds Epic via the ProgramData manifest directory', async () => {
    const r = await new EpicAdapter(windowsOs()).probe();
    expect(r.status).toBe('installed');
    expect(r.manifestDir).toBe(MANIFEST_DIR);
    expect(r.detectedVia).toContain('ProgramData');
  });

  it('reports unavailable when the manifest dir is absent', async () => {
    const os = new FakeEpicOs();
    os.platform = 'win32';
    os.setEnv('ProgramData', 'C:\\ProgramData');
    const r = await new EpicAdapter(os).probe();
    expect(r.status).toBe('unavailable');
    expect(r.reason).toContain('not found');
  });

  it('degrades honestly off Windows', async () => {
    const os = new FakeEpicOs();
    os.platform = 'linux';
    const r = await new EpicAdapter(os).probe();
    expect(r.status).toBe('unavailable');
    expect(r.reason).toContain('Windows');
  });
});

describe('scan', () => {
  function tree(): FakeEpicOs {
    const os = windowsOs();
    os.addFile(
      `${MANIFEST_DIR}\\deadbeef1234.cafef00d5678.item`,
      itemManifest({ AppName: 'Fortnite', DisplayName: 'Fortnite' }),
    );
    os.addDir('C:\\Program Files\\Epic Games\\Fortnite');
    os.addFile(
      `${MANIFEST_DIR}\\aaaabbbb.ccccdddd.item`,
      itemManifest({
        AppName: 'RocketLeague',
        DisplayName: 'Rocket League',
        InstallLocation: 'D:\\Games\\RocketLeague',
      }),
    );
    // Install dir intentionally absent → present=false, still discovered.
    return os;
  }

  it('discovers installed items from .item manifests', async () => {
    const r = await new EpicAdapter(tree()).scan();
    expect(r.status).toBe('completed');
    expect(r.games).toHaveLength(2);
    const fn = r.games.find((g) => g.appName === 'Fortnite')!;
    expect(fn.title).toBe('Fortnite');
    expect(fn.installLocation).toBe('C:\\Program Files\\Epic Games\\Fortnite');
    expect(fn.present).toBe(true);
    const rl = r.games.find((g) => g.appName === 'RocketLeague')!;
    expect(rl.present).toBe(false);
  });

  it('skips malformed and hostile manifests with warnings', async () => {
    const os = tree();
    os.addFile(`${MANIFEST_DIR}\\bad.item`, '{not json');
    os.addFile(
      `${MANIFEST_DIR}\\evil.item`,
      itemManifest({ AppName: 'Evil', InstallLocation: 'C:\\Games\\..\\Windows' }),
    );
    os.addFile(`${MANIFEST_DIR}\\notes.txt`, 'not a manifest');
    const r = await new EpicAdapter(os).scan();
    expect(r.status).toBe('completed');
    expect(r.games).toHaveLength(2);
    expect(r.warnings.length).toBeGreaterThanOrEqual(2);
  });

  it('fails honestly when Epic is absent', async () => {
    const r = await new EpicAdapter(new FakeEpicOs()).scan();
    expect(r.status).toBe('failed');
    expect(r.error).toContain('not found');
  });

  it('honors cancellation between manifests', async () => {
    const os = tree();
    const adapter = new EpicAdapter(os);
    const token = { cancelled: true };
    const r = await adapter.scan(token);
    expect(r.status).toBe('cancelled');
  });
});

describe('validateLaunch', () => {
  it('always reports open-client — per-game deep links are unverified', async () => {
    const v = new EpicAdapter(windowsOs()).validateLaunch();
    expect(v.capability).toBe('open-client');
    expect(v.uri).toBe(EPIC_LAUNCHER_URI);
    expect(v.reason).toContain('not verified');
  });

  it('uses the documented launcher scheme', async () => {
    expect(EPIC_LAUNCHER_URI).toBe('com.epicgames.launcher://');
  });
});
