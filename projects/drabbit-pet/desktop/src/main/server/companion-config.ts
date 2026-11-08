import { randomBytes } from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';

/**
 * Owns `companion.json` in userData: the companion server's settings.
 * Same pattern as SaveStore — atomic writes (temp + rename), a corrupt
 * file is renamed aside (never silently destroyed) and defaults are
 * used. The filesystem is injectable so tests can run against a temp
 * directory or a fake.
 *
 * The token is a secret (project AGENTS.md rule 8): it lives only in
 * this file and in the care panel UI. Never log it.
 */

export const COMPANION_FILENAME = 'companion.json';

export interface CompanionConfig {
  /** Master switch — the server runs only when true. Default false. */
  enabled: boolean;
  /** Bind address. "0.0.0.0" = LAN + Tailscale; token is the gate. */
  host: string;
  port: number;
  /** Bearer token; '' until first generated (lazily, on first enable). */
  token: string;
}

export const DEFAULT_COMPANION_CONFIG: CompanionConfig = {
  enabled: false,
  host: '0.0.0.0',
  port: 8931,
  token: '',
};

/** 32 random bytes, base64url — the pairing token for the phone. */
export function generateCompanionToken(): string {
  return randomBytes(32).toString('base64url');
}

/** The subset of node:fs the store uses — injectable for tests. */
export interface CompanionFs {
  readFileSync(filePath: string, encoding: 'utf8'): string;
  writeFileSync(filePath: string, data: string, encoding: 'utf8'): void;
  renameSync(from: string, to: string): void;
  mkdirSync(dirPath: string, options: { recursive: boolean }): void;
}

const nodeFs: CompanionFs = {
  readFileSync: (p, enc) => fs.readFileSync(p, enc),
  writeFileSync: (p, data, enc) => fs.writeFileSync(p, data, enc),
  renameSync: (from, to) => fs.renameSync(from, to),
  mkdirSync: (p, options) => {
    fs.mkdirSync(p, options);
  },
};

export type CompanionLoadOutcome = 'loaded' | 'fresh-missing' | 'fresh-corrupt';

export interface CompanionLoadResult {
  config: CompanionConfig;
  outcome: CompanionLoadOutcome;
  /** Where a corrupt config was preserved (only for 'fresh-corrupt'). */
  backupPath?: string;
}

function isValidConfig(v: unknown): v is CompanionConfig {
  if (typeof v !== 'object' || v === null || Array.isArray(v)) return false;
  const c = v as Record<string, unknown>;
  return (
    typeof c.enabled === 'boolean' &&
    typeof c.host === 'string' &&
    c.host.length > 0 &&
    typeof c.port === 'number' &&
    Number.isInteger(c.port) &&
    c.port >= 1 &&
    c.port <= 65535 &&
    typeof c.token === 'string'
  );
}

export class CompanionConfigStore {
  readonly filePath: string;

  constructor(
    dir: string,
    private readonly opts: {
      fs?: CompanionFs;
      log?: (msg: string) => void;
    } = {},
  ) {
    this.filePath = path.join(dir, COMPANION_FILENAME);
  }

  private get fs(): CompanionFs {
    return this.opts.fs ?? nodeFs;
  }

  private log(msg: string): void {
    this.opts.log?.(msg);
  }

  /**
   * Load the config, or fall back to defaults:
   * - missing file → defaults (first run; nothing is written yet)
   * - unparseable / invalid file → renamed aside, defaults used,
   *   recovery logged (the token is NOT part of the log line).
   */
  load(nowMs: number): CompanionLoadResult {
    let text: string;
    try {
      text = this.fs.readFileSync(this.filePath, 'utf8');
    } catch {
      return { config: { ...DEFAULT_COMPANION_CONFIG }, outcome: 'fresh-missing' };
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
      `companion.corrupt-${nowMs}.json`,
    );
    try {
      this.fs.renameSync(this.filePath, backupPath);
      this.log(
        `[drabbit] companion config was corrupt; preserved at ${backupPath} and using defaults`,
      );
    } catch {
      this.log('[drabbit] WARNING: companion config corrupt and could not be moved aside');
    }
    const result: CompanionLoadResult = {
      config: { ...DEFAULT_COMPANION_CONFIG },
      outcome: 'fresh-corrupt',
    };
    result.backupPath = backupPath;
    return result;
  }

  /** Atomic write: temp file → rename over the config. */
  save(config: CompanionConfig): void {
    this.fs.mkdirSync(path.dirname(this.filePath), { recursive: true });
    const tmp = `${this.filePath}.tmp`;
    this.fs.writeFileSync(tmp, `${JSON.stringify(config, null, 2)}\n`, 'utf8');
    this.fs.renameSync(tmp, this.filePath);
  }
}
