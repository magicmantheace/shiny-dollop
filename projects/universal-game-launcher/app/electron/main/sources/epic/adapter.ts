/**
 * Epic Games source adapter.
 *
 * Implements the scanner adapter contract from docs/ARCHITECTURE.md:
 * probe() → scan() → validateLaunch() → launch(), with honest capability
 * reporting at every step. All OS access goes through the injectable EpicOs
 * layer, so the adapter is fully testable on any platform.
 *
 * Launch honesty: per-game Epic deep links are NOT verified against
 * documentation or a real client, so they are not used. Discovered games
 * get the `open-client` capability: the clearly labeled action opens the
 * Epic Games Launcher via its documented `com.epicgames.launcher://`
 * scheme and the game is never reported as running.
 *
 * Security: manifests are data, never commands. Only whitelisted fields
 * are read (see manifest.ts); install locations are validated and never
 * executed.
 */
import type { LaunchCapability } from '../../../../shared/types';
import { EpicFsError, joinFor, manifestDirFor, type EpicOs } from './os';
import { parseEpicManifest } from './manifest';

export type ProbeStatus = 'installed' | 'unavailable';

export interface ProbeResult {
  status: ProbeStatus;
  /** Human-readable reason, including the detection method and paths checked. */
  reason: string;
  /** Manifest directory when found. */
  manifestDir: string | null;
  /** Which candidate located Epic, e.g. "%ProgramData%\\Epic\\EpicGamesLauncher\\Data\\Manifests". */
  detectedVia: string | null;
}

export interface DiscoveredGame {
  /** Epic AppName id string (from the manifest). */
  appName: string;
  title: string;
  /** Absolute install location as written in the manifest. */
  installLocation: string;
  /** Whether the install location currently exists on disk. */
  present: boolean;
}

export type ScanStatus = 'completed' | 'cancelled' | 'failed';

export interface ScanResult {
  status: ScanStatus;
  games: DiscoveredGame[];
  warnings: string[];
  /** Set when status is 'failed'. */
  error: string | null;
  scannedAt: string;
}

export interface LaunchValidation {
  capability: LaunchCapability;
  /** Validated launcher URI when capability is 'open-client'. */
  uri: string | null;
  reason: string;
}

export interface ScanController {
  /** Flip to request cancellation; the scan stops between manifests. */
  readonly token: { cancelled: boolean };
  cancel(): void;
}

export function createEpicScanController(): ScanController {
  const token = { cancelled: false };
  return { token, cancel: () => { token.cancelled = true; } };
}

const MAX_MANIFEST_BYTES = 1024 * 1024;
const MAX_MANIFESTS = 5000;
const MANIFEST_RE = /\.item$/i;

/**
 * Documented Epic Games Launcher protocol. Opens the launcher; it does NOT
 * launch a specific game and must never be presented as a game launch.
 */
export const EPIC_LAUNCHER_URI = 'com.epicgames.launcher://';

export class EpicAdapter {
  constructor(private readonly os: EpicOs) {}

  /**
   * Locate Epic's manifest directory. Read-only; never writes anything.
   */
  probe(): ProbeResult {
    const os = this.os;
    const dir = manifestDirFor(os);
    const label = '%ProgramData%\\Epic\\EpicGamesLauncher\\Data\\Manifests';
    if (dir && os.isDirectory(dir)) {
      return {
        status: 'installed',
        reason: `Epic manifest directory found at ${dir} (via ${label}).`,
        manifestDir: dir,
        detectedVia: label,
      };
    }
    const where =
      os.platform === 'win32'
        ? `Checked: ${label}${dir ? ` (${dir})` : ' (ProgramData unavailable)'}.`
        : 'Epic detection needs Windows — the ProgramData manifest location is unavailable on this platform.';
    return {
      status: 'unavailable',
      reason: `Epic Games Launcher manifests not found. ${where}`,
      manifestDir: null,
      detectedVia: null,
    };
  }

  /**
   * Discover installed Epic items from local `.item` manifests.
   * Side-effect-free local reads only. Bounded (manifest count + file size)
   * and cancellable via token.
   */
  scan(token?: { cancelled: boolean }): ScanResult {
    const os = this.os;
    const scannedAt = new Date().toISOString();
    const probe = this.probe();
    if (probe.status !== 'installed' || !probe.manifestDir) {
      return { status: 'failed', games: [], warnings: [], error: probe.reason, scannedAt };
    }
    const manifestDir = probe.manifestDir;
    const warnings: string[] = [];
    const games: DiscoveredGame[] = [];
    const seenAppNames = new Set<string>();

    let names: string[];
    try {
      names = os.listDirNames(manifestDir);
    } catch (err) {
      return {
        status: 'failed',
        games: [],
        warnings,
        error: `Could not list ${manifestDir} (${err instanceof EpicFsError ? err.code : 'error'}).`,
        scannedAt,
      };
    }

    let manifestCount = 0;
    for (const name of names) {
      if (token?.cancelled) {
        return { status: 'cancelled', games, warnings, error: null, scannedAt };
      }
      if (!MANIFEST_RE.test(name)) continue;
      if (seenAppNames.has(name.toLowerCase())) continue;
      if (++manifestCount > MAX_MANIFESTS) {
        warnings.push(`More than ${MAX_MANIFESTS} manifests; remaining ones skipped.`);
        return { status: 'completed', games, warnings, error: null, scannedAt };
      }
      const itemPath = joinFor(os.platform, manifestDir, name);
      let text: string;
      try {
        text = os.readTextFile(itemPath, MAX_MANIFEST_BYTES);
      } catch (err) {
        warnings.push(
          `Skipped unreadable manifest ${name} (${err instanceof EpicFsError ? err.code : 'error'}).`,
        );
        continue;
      }
      const parsed = parseEpicManifest(text, os.platform);
      if (!parsed.ok) {
        warnings.push(`Skipped manifest ${name}: ${parsed.error.code} — ${parsed.error.detail}`);
        continue;
      }
      warnings.push(...parsed.warnings.map((w: string) => `${name}: ${w}`));
      const m = parsed.manifest;
      const key = m.appName.toLowerCase();
      if (seenAppNames.has(key)) {
        warnings.push(`Duplicate manifest for AppName ${m.appName}; kept the first.`);
        continue;
      }
      seenAppNames.add(key);
      games.push({
        appName: m.appName,
        title: m.displayName,
        installLocation: m.installLocation,
        present: os.isDirectory(m.installLocation),
      });
    }
    return { status: 'completed', games, warnings, error: null, scannedAt };
  }

  /**
   * Classify what launching this game can do. Per-game deep links are not
   * verified, so every Epic game gets the honest open-client capability.
   * No side effects.
   */
  validateLaunch(): LaunchValidation {
    return {
      capability: 'open-client',
      uri: EPIC_LAUNCHER_URI,
      reason:
        'Per-game Epic launch links are not verified, so this opens the Epic Games Launcher ' +
        'instead of claiming a direct game launch.',
    };
  }
}
