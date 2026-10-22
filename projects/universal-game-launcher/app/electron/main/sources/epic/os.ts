/**
 * OS access layer for the Epic Games adapter.
 *
 * All Epic filesystem reads go through this interface so the adapter is
 * fully testable with a fake on any platform. The real implementation
 * degrades honestly off Windows: the ProgramData candidate path simply
 * won't exist there.
 */
import fs from 'node:fs';
import path from 'node:path';

export class EpicFsError extends Error {
  readonly code: string;
  constructor(code: string, message: string) {
    super(message);
    this.name = 'EpicFsError';
    this.code = code;
  }
}

export interface EpicOs {
  readonly platform: NodeJS.Platform;
  /** Read an environment variable. */
  env(name: string): string | undefined;
  isDirectory(p: string): boolean;
  isFile(p: string): boolean;
  /** Read a text file, bounded by maxBytes. Throws EpicFsError on any failure. */
  readTextFile(p: string, maxBytes: number): string;
  /** Bare entry names of a directory. Throws EpicFsError on any failure. */
  listDirNames(p: string): string[];
}

export class RealEpicOs implements EpicOs {
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

  isDirectory(p: string): boolean {
    try {
      return fs.statSync(p).isDirectory();
    } catch {
      return false;
    }
  }

  isFile(p: string): boolean {
    try {
      return fs.statSync(p).isFile();
    } catch {
      return false;
    }
  }

  readTextFile(p: string, maxBytes: number): string {
    let stat: fs.Stats;
    try {
      stat = fs.statSync(p);
    } catch {
      throw new EpicFsError('NOT_FOUND', `File not found: ${p}`);
    }
    if (!stat.isFile()) throw new EpicFsError('NOT_A_FILE', `Not a file: ${p}`);
    if (stat.size > maxBytes) {
      throw new EpicFsError('TOO_LARGE', `File exceeds ${maxBytes} bytes: ${p}`);
    }
    try {
      // Epic writes manifests as UTF-8 (sometimes with BOM); strip the BOM.
      return fs.readFileSync(p, 'utf8').replace(/^﻿/, '');
    } catch (err) {
      throw new EpicFsError('READ_FAILED', `Could not read ${p}: ${(err as Error).message}`);
    }
  }

  listDirNames(p: string): string[] {
    try {
      return fs.readdirSync(p);
    } catch (err) {
      throw new EpicFsError(
        'LIST_FAILED',
        `Could not list directory ${p}: ${(err as Error).message}`,
      );
    }
  }
}

/**
 * Standard location of Epic's installed-item manifests on Windows:
 * %ProgramData%\Epic\EpicGamesLauncher\Data\Manifests\*.item
 */
export function manifestDirFor(os: EpicOs): string | null {
  const programData = os.env('ProgramData');
  if (!programData) return null;
  return joinFor(os.platform, programData, 'Epic', 'EpicGamesLauncher', 'Data', 'Manifests');
}

/** Join path segments with the OS separator of the given platform. */
export function joinFor(platform: NodeJS.Platform, ...parts: string[]): string {
  return platform === 'win32' ? parts.join('\\') : path.posix.join(...parts);
}
