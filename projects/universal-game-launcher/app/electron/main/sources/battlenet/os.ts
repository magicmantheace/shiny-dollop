/**
 * OS access layer for the Battle.net adapter.
 *
 * Kept deliberately small: the adapter only needs to locate the Battle.net
 * client executable. All access goes through this interface so the adapter
 * is fully testable with a fake on any platform.
 */
import fs from 'node:fs';

export interface BattleNetOs {
  readonly platform: NodeJS.Platform;
  /** Read an environment variable. */
  env(name: string): string | undefined;
  isFile(p: string): boolean;
}

export class RealBattleNetOs implements BattleNetOs {
  readonly platform: NodeJS.Platform = process.platform;

  env(name: string): string | undefined {
    if (this.platform === 'win32') {
      const want = name.toLowerCase();
      for (const k of Object.keys(process.env)) {
        if (k.toLowerCase() === want) return process.env[k];
      }
      return undefined;
    }
    return process.env[name];
  }

  isFile(p: string): boolean {
    try {
      return fs.statSync(p).isFile();
    } catch {
      return false;
    }
  }
}

/** Join path segments with the OS separator of the given platform. */
export function joinFor(platform: NodeJS.Platform, ...parts: string[]): string {
  return parts.join(platform === 'win32' ? '\\' : '/');
}
