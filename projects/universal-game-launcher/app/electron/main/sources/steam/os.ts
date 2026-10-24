/**
 * OS access layer for the Steam adapter.
 *
 * All Steam filesystem/registry reads go through this interface so the
 * adapter is fully testable with a fake on any platform. The real
 * implementation degrades honestly off Windows: registry reads are skipped
 * and Windows-only candidate paths simply won't exist.
 *
 * Filesystem methods are async (Promise-based) so scans never block the
 * Electron main thread: the adapter yields to the event loop between
 * manifests, which keeps the UI responsive and lets cancellation IPC
 * requests be processed promptly.
 */
import fsp from 'node:fs/promises';
import path from 'node:path';
import { execFile } from 'node:child_process';

export class SteamFsError extends Error {
  readonly code: string;
  constructor(code: string, message: string) {
    super(message);
    this.name = 'SteamFsError';
    this.code = code;
  }
}

export interface SteamOs {
  readonly platform: NodeJS.Platform;
  /** Read an environment variable. */
  env(name: string): string | undefined;
  isDirectory(p: string): Promise<boolean>;
  isFile(p: string): Promise<boolean>;
  /** Read a text file, bounded by maxBytes. Throws SteamFsError on any failure. */
  readTextFile(p: string, maxBytes: number): Promise<string>;
  /** Bare entry names of a directory. Throws SteamFsError on any failure. */
  listDirNames(p: string): Promise<string[]>;
  /**
   * Read a REG_SZ/REG_EXPAND_SZ string value. Returns null when unavailable.
   * Only meaningful on Windows; the real implementation returns null elsewhere.
   */
  queryRegistryString(hive: 'HKCU' | 'HKLM', keyPath: string, valueName: string): Promise<string | null>;
}

export function parseRegQueryOutput(stdout: string, valueName: string): string | null {
  const wanted = valueName.toLowerCase();
  for (const line of stdout.split(/\r?\n/)) {
    const m = line.match(/^\s*(\S+)\s+REG_(?:SZ|EXPAND_SZ)\s+(.+?)\s*$/);
    if (m && m[1]!.toLowerCase() === wanted) {
      return m[2]!.trim() || null;
    }
  }
  return null;
}

export class RealSteamOs implements SteamOs {
  readonly platform: NodeJS.Platform = process.platform;

  env(name: string): string | undefined {
    // On Windows, env lookups are case-insensitive; normalize for tests too.
    if (this.platform === 'win32') {
      const want = name.toLowerCase();
      for (const k of Object.keys(process.env)) {
        if (k.toLowerCase() === want) return process.env[k];
      }
      return undefined;
    }
    return process.env[name];
  }

  isDirectory(p: string): Promise<boolean> {
    return fsp
      .stat(p)
      .then((s) => s.isDirectory())
      .catch(() => false);
  }

  isFile(p: string): Promise<boolean> {
    return fsp
      .stat(p)
      .then((s) => s.isFile())
      .catch(() => false);
  }

  async readTextFile(p: string, maxBytes: number): Promise<string> {
    let stat: { isFile(): boolean; size: number };
    try {
      stat = await fsp.stat(p);
    } catch {
      throw new SteamFsError('NOT_FOUND', `File not found: ${p}`);
    }
    if (!stat.isFile()) throw new SteamFsError('NOT_A_FILE', `Not a file: ${p}`);
    if (stat.size > maxBytes) {
      throw new SteamFsError('TOO_LARGE', `File exceeds ${maxBytes} bytes: ${p}`);
    }
    try {
      // Steam writes VDF/ACF as UTF-8 (sometimes with BOM); strip the BOM.
      return (await fsp.readFile(p, 'utf8')).replace(/^﻿/, '');
    } catch (err) {
      throw new SteamFsError(
        'READ_FAILED',
        `Could not read ${p}: ${(err as Error).message}`,
      );
    }
  }

  async listDirNames(p: string): Promise<string[]> {
    try {
      return await fsp.readdir(p);
    } catch (err) {
      throw new SteamFsError(
        'LIST_FAILED',
        `Could not list directory ${p}: ${(err as Error).message}`,
      );
    }
  }

  queryRegistryString(
    hive: 'HKCU' | 'HKLM',
    keyPath: string,
    valueName: string,
  ): Promise<string | null> {
    if (this.platform !== 'win32') return Promise.resolve(null);
    // Structured argv, shell:false — no string-built command line.
    return new Promise((resolve) => {
      execFile(
        'reg',
        ['query', `${hive}\\${keyPath}`, '/v', valueName],
        { shell: false, windowsHide: true, encoding: 'utf8', timeout: 8000 },
        (err, stdout) => {
          if (err) return resolve(null);
          resolve(parseRegQueryOutput(String(stdout), valueName));
        },
      );
    });
  }
}

/** Candidate Steam install locations, in priority order. Registry last. */
export interface SteamCandidate {
  kind: 'path' | 'registry';
  description: string;
}

export function describeCandidates(): SteamCandidate[] {
  return [
    { kind: 'path', description: '%ProgramFiles(x86)%\\Steam' },
    { kind: 'path', description: '%ProgramFiles%\\Steam' },
    { kind: 'registry', description: 'HKCU\\Software\\Valve\\Steam → SteamPath' },
    { kind: 'registry', description: 'HKLM\\SOFTWARE\\Wow6432Node\\Valve\\Steam → InstallPath' },
    { kind: 'registry', description: 'HKLM\\SOFTWARE\\Valve\\Steam → InstallPath' },
  ];
}

/** Join path segments with the OS separator of the given platform. */
export function joinFor(platform: NodeJS.Platform, ...parts: string[]): string {
  return platform === 'win32' ? parts.join('\\') : path.posix.join(...parts);
}
