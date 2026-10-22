/** Fake SteamOs backed by in-memory data — lets adapter tests run on any platform. */
import { SteamFsError, type SteamOs } from '../electron/main/sources/steam/os';

function norm(p: string): string {
  return p.replace(/\\/g, '/').toLowerCase();
}

export class FakeSteamOs implements SteamOs {
  platform: NodeJS.Platform = 'win32';
  private files = new Map<string, string>();
  private dirs = new Set<string>();
  private registry = new Map<string, string>();
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
    // Implicitly create parent dirs.
    const parts = norm(p).split('/');
    for (let i = 1; i < parts.length; i++) {
      this.dirs.add(parts.slice(0, i).join('/'));
    }
    return this;
  }

  setRegistry(hive: 'HKCU' | 'HKLM', keyPath: string, valueName: string, data: string): this {
    this.registry.set(`${hive}\\${keyPath}\\${valueName}`.toLowerCase(), data);
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
    if (content === undefined) throw new SteamFsError('NOT_FOUND', `File not found: ${p}`);
    if (content.length > maxBytes) throw new SteamFsError('TOO_LARGE', `File too large: ${p}`);
    return content;
  }

  listDirNames(p: string): string[] {
    const prefix = norm(p).replace(/\/$/, '') + '/';
    if (!this.dirs.has(norm(p))) {
      throw new SteamFsError('LIST_FAILED', `Could not list directory ${p}`);
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

  queryRegistryString(hive: 'HKCU' | 'HKLM', keyPath: string, valueName: string): string | null {
    if (this.platform !== 'win32') return null;
    return this.registry.get(`${hive}\\${keyPath}\\${valueName}`.toLowerCase()) ?? null;
  }
}

/** Build a minimal fake Steam install: steam.exe + steamapps dir. */
export function fakeSteamInstall(os: FakeSteamOs, steamDir: string): FakeSteamOs {
  os.addDir(steamDir);
  os.addFile(`${steamDir}\\steam.exe`, 'fake-binary');
  os.addDir(`${steamDir}\\steamapps`);
  os.addDir(`${steamDir}\\steamapps\\common`);
  return os;
}

export function acf(appid: string, name: string, installdir: string): string {
  return `"AppState"
{
\t"appid"\t\t"${appid}"
\t"name"\t\t"${name}"
\t"installdir"\t\t"${installdir}"
}`;
}

export function libraryFoldersVdf(folders: string[]): string {
  const entries = folders
    .map((f, i) => `\t"${i}"\n\t{\n\t\t"path"\t\t"${f.replace(/\\/g, '\\\\')}"\n\t}`)
    .join('\n');
  return `"libraryfolders"\n{\n${entries}\n}`;
}
