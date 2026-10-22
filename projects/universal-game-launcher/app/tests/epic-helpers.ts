/** Fake EpicOs backed by in-memory data — lets adapter tests run on any platform. */
import { EpicFsError, type EpicOs } from '../electron/main/sources/epic/os';

function norm(p: string): string {
  return p.replace(/\\/g, '/').toLowerCase();
}

export class FakeEpicOs implements EpicOs {
  platform: NodeJS.Platform = 'win32';
  private files = new Map<string, string>();
  private dirs = new Set<string>();
  private envVars = new Map<string, string>();

  setEnv(name: string, value: string): this {
    this.envVars.set(name.toLowerCase(), value);
    return this;
  }

  addDir(p: string): this {
    this.dirs.add(norm(p));
    return this;
  }

  addFile(p: string, content: string): this {
    this.files.set(norm(p), content);
    const parts = norm(p).split('/');
    for (let i = 1; i < parts.length; i++) {
      this.dirs.add(parts.slice(0, i).join('/'));
    }
    return this;
  }

  env(name: string): string | undefined {
    return this.envVars.get(name.toLowerCase());
  }

  isDirectory(p: string): boolean {
    return this.dirs.has(norm(p));
  }

  isFile(p: string): boolean {
    return this.files.has(norm(p));
  }

  readTextFile(p: string, maxBytes: number): string {
    const key = norm(p);
    const content = this.files.get(key);
    if (content === undefined) throw new EpicFsError('NOT_FOUND', `File not found: ${p}`);
    if (content.length > maxBytes) throw new EpicFsError('TOO_LARGE', `File too large: ${p}`);
    return content;
  }

  listDirNames(p: string): string[] {
    const prefix = norm(p).replace(/\/$/, '') + '/';
    if (!this.dirs.has(norm(p))) {
      throw new EpicFsError('LIST_FAILED', `Could not list directory ${p}`);
    }
    const names = new Set<string>();
    for (const f of this.files.keys()) {
      if (f.startsWith(prefix)) {
        const rest = f.slice(prefix.length);
        if (rest && !rest.includes('/')) names.add(rest);
      }
    }
    for (const d of this.dirs) {
      if (d.startsWith(prefix)) {
        const rest = d.slice(prefix.length);
        if (rest && !rest.includes('/')) names.add(rest);
      }
    }
    return [...names];
  }
}

export const MANIFEST_DIR = 'C:\\ProgramData\\Epic\\EpicGamesLauncher\\Data\\Manifests';

/** Build a fake Epic install: manifest dir with ProgramData set. */
export function fakeEpicInstall(os: FakeEpicOs, manifestDir: string = MANIFEST_DIR): FakeEpicOs {
  os.setEnv('ProgramData', 'C:\\ProgramData');
  os.addDir(manifestDir);
  return os;
}

/** Build a minimal well-formed .item manifest. */
export function itemManifest(overrides: Record<string, unknown> = {}): string {
  return JSON.stringify({
    FormatVersion: 0,
    bIsManaged: false,
    bIsApplication: true,
    CatalogNamespace: 'deadbeef1234',
    CatalogItemId: 'cafef00d5678',
    AppName: 'Fortnite',
    AppVersionString: '++Fortnite+Release-36.00',
    DisplayName: 'Fortnite',
    InstallLocation: 'C:\\Program Files\\Epic Games\\Fortnite',
    ...overrides,
  });
}
