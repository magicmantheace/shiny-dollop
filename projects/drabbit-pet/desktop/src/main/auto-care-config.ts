import fs from 'node:fs';
import path from 'node:path';

/**
 * Owns `auto-care.json` in userData: the auto-care master switch.
 * Same pattern as the companion config store — atomic writes (temp
 * + rename); a corrupt file is renamed aside (never silently
 * destroyed) and the default (off) is used.
 */

export const AUTO_CARE_FILENAME = 'auto-care.json';

export interface AutoCareConfig {
  /** Master switch — auto-care acts only when true. Default false. */
  enabled: boolean;
}

export const DEFAULT_AUTO_CARE_CONFIG: AutoCareConfig = { enabled: false };

/** The subset of node:fs the store uses — injectable for tests. */
export interface AutoCareFs {
  readFileSync(filePath: string, encoding: 'utf8'): string;
  writeFileSync(filePath: string, data: string, encoding: 'utf8'): void;
  renameSync(from: string, to: string): void;
  mkdirSync(dirPath: string, options: { recursive: boolean }): void;
}

const nodeFs: AutoCareFs = {
  readFileSync: (p, enc) => fs.readFileSync(p, enc),
  writeFileSync: (p, data, enc) => fs.writeFileSync(p, data, enc),
  renameSync: (from, to) => fs.renameSync(from, to),
  mkdirSync: (p, options) => {
    fs.mkdirSync(p, options);
  },
};

export type AutoCareLoadOutcome = 'loaded' | 'fresh-missing' | 'fresh-corrupt';

export interface AutoCareLoadResult {
  config: AutoCareConfig;
  outcome: AutoCareLoadOutcome;
  backupPath?: string;
}

function isValidConfig(v: unknown): v is AutoCareConfig {
  if (typeof v !== 'object' || v === null || Array.isArray(v)) return false;
  return typeof (v as Record<string, unknown>).enabled === 'boolean';
}

export class AutoCareConfigStore {
  readonly filePath: string;

  constructor(
    dir: string,
    private readonly opts: {
      fs?: AutoCareFs;
      log?: (msg: string) => void;
    } = {},
  ) {
    this.filePath = path.join(dir, AUTO_CARE_FILENAME);
  }

  private get fs(): AutoCareFs {
    return this.opts.fs ?? nodeFs;
  }

  private log(msg: string): void {
    this.opts.log?.(msg);
  }

  load(nowMs: number): AutoCareLoadResult {
    let text: string;
    try {
      text = this.fs.readFileSync(this.filePath, 'utf8');
    } catch {
      return { config: { ...DEFAULT_AUTO_CARE_CONFIG }, outcome: 'fresh-missing' };
    }
    let parsed: unknown;
    try {
      parsed = JSON.parse(text);
    } catch {
      parsed = undefined;
    }
    if (isValidConfig(parsed)) {
      return { config: { ...parsed }, outcome: 'loaded' };
    }
    const backupPath = path.join(
      path.dirname(this.filePath),
      `auto-care.corrupt-${nowMs}.json`,
    );
    try {
      this.fs.renameSync(this.filePath, backupPath);
      this.log(
        `[drabbit] auto-care config was corrupt; preserved at ${backupPath} and using defaults`,
      );
    } catch {
      this.log('[drabbit] WARNING: auto-care config corrupt and could not be moved aside');
    }
    const result: AutoCareLoadResult = {
      config: { ...DEFAULT_AUTO_CARE_CONFIG },
      outcome: 'fresh-corrupt',
    };
    result.backupPath = backupPath;
    return result;
  }

  /** Atomic write: temp file → rename over the config. */
  save(config: AutoCareConfig): void {
    this.fs.mkdirSync(path.dirname(this.filePath), { recursive: true });
    const tmp = `${this.filePath}.tmp`;
    this.fs.writeFileSync(tmp, `${JSON.stringify(config, null, 2)}\n`, 'utf8');
    this.fs.renameSync(tmp, this.filePath);
  }
}
