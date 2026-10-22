/** Fake BattleNetOs backed by in-memory data. */
import type { BattleNetOs } from '../electron/main/sources/battlenet/os';

export class FakeBattleNetOs implements BattleNetOs {
  platform: NodeJS.Platform = 'win32';
  private files = new Set<string>();
  private envVars = new Map<string, string>();

  setEnv(name: string, value: string): this {
    this.envVars.set(name.toLowerCase(), value);
    return this;
  }

  addFile(p: string): this {
    this.files.add(p.replace(/\\/g, '/').toLowerCase());
    return this;
  }

  env(name: string): string | undefined {
    return this.envVars.get(name.toLowerCase());
  }

  isFile(p: string): boolean {
    return this.files.has(p.replace(/\\/g, '/').toLowerCase());
  }
}

/** Build a fake Battle.net client install. */
export function fakeBattleNetInstall(os: FakeBattleNetOs): FakeBattleNetOs {
  os.setEnv('ProgramFiles(x86)', 'C:\\Program Files (x86)');
  os.addFile('C:\\Program Files (x86)\\Battle.net\\Battle.net.exe');
  return os;
}
