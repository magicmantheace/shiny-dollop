/**
 * Steam source adapter.
 *
 * Implements the scanner adapter contract from docs/ARCHITECTURE.md:
 * probe() → scan() → validateLaunch() → launch(), with honest capability
 * reporting at every step. All OS access goes through the injectable SteamOs
 * layer, so the adapter is fully testable on any platform.
 *
 * Security: manifests are data, never commands. AppIDs are validated as
 * decimal digits before any URI is built. installdir values are rejected
 * when absolute or escaping (see vdf.ts).
 */
import type { LaunchCapability } from '../../../../shared/types';
import { parseAppManifest, parseLibraryFolders, parseVdf } from './vdf';
import { SteamFsError, joinFor, type SteamOs } from './os';

export type ProbeStatus = 'installed' | 'unavailable';

export interface ProbeResult {
  status: ProbeStatus;
  /** Human-readable reason, including the detection method and paths checked. */
  reason: string;
  /** Steam install dir when found. */
  steamDir: string | null;
  /** Which candidate located Steam, e.g. "%ProgramFiles(x86)%\Steam". */
  detectedVia: string | null;
}

export interface DiscoveredGame {
  /** Decimal Steam AppID (from the manifest file name). */
  appid: string;
  title: string;
  /** Absolute install directory (.../steamapps/common/<installdir>). */
  installDir: string;
  /** Whether the install directory currently exists on disk. */
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
  /** Validated steam:// URI when capability is 'native-uri'. */
  uri: string | null;
  reason: string;
}

export interface ScanController {
  /** Flip to request cancellation; the scan stops between manifests. */
  readonly token: { cancelled: boolean };
  cancel(): void;
}

export function createScanController(): ScanController {
  const token = { cancelled: false };
  return { token, cancel: () => { token.cancelled = true; } };
}

const MAX_MANIFEST_BYTES = 1024 * 1024;
const MAX_MANIFESTS = 5000;
const MANIFEST_RE = /^appmanifest_(\d+)\.acf$/i;

/** Steam AppIDs are decimal integers. Reject anything else before building a URI. */
export function isValidAppId(value: unknown): value is string {
  return typeof value === 'string' && /^\d{1,10}$/.test(value);
}

/** Build steam://rungameid/<appid>. Call only after isValidAppId. */
export function buildRunGameUri(appid: string): string {
  if (!isValidAppId(appid)) {
    throw new Error(`Refusing to build a Steam URI for invalid AppID: ${String(appid)}`);
  }
  return `steam://rungameid/${appid}`;
}

export class SteamAdapter {
  constructor(private readonly os: SteamOs) {}

  /**
   * Locate the Steam installation. Checks well-known install dirs first,
   * then read-only registry keys (Windows only). Never writes anything.
   */
  probe(): ProbeResult {
    const os = this.os;
    const checked: string[] = [];
    const exeName = 'steam.exe';

    const pathCandidates: Array<{ dir: string | undefined; label: string }> = [
      { dir: joinFor(os.platform, os.env('ProgramFiles(x86)') ?? '', 'Steam'), label: '%ProgramFiles(x86)%\\Steam' },
      { dir: joinFor(os.platform, os.env('ProgramFiles') ?? '', 'Steam'), label: '%ProgramFiles%\\Steam' },
    ];
    for (const c of pathCandidates) {
      if (!c.dir) continue;
      checked.push(c.label);
      if (os.isFile(joinFor(os.platform, c.dir, exeName))) {
        return {
          status: 'installed',
          reason: `Steam found at ${c.dir} (via ${c.label}).`,
          steamDir: c.dir,
          detectedVia: c.label,
        };
      }
    }

    const regCandidates: Array<{ hive: 'HKCU' | 'HKLM'; key: string; value: string; label: string }> = [
      { hive: 'HKCU', key: 'Software\\Valve\\Steam', value: 'SteamPath', label: 'HKCU\\Software\\Valve\\Steam → SteamPath' },
      { hive: 'HKLM', key: 'SOFTWARE\\Wow6432Node\\Valve\\Steam', value: 'InstallPath', label: 'HKLM\\SOFTWARE\\Wow6432Node\\Valve\\Steam → InstallPath' },
      { hive: 'HKLM', key: 'SOFTWARE\\Valve\\Steam', value: 'InstallPath', label: 'HKLM\\SOFTWARE\\Valve\\Steam → InstallPath' },
    ];
    for (const c of regCandidates) {
      checked.push(c.label);
      const dir = os.queryRegistryString(c.hive, c.key, c.value);
      if (dir && os.isFile(joinFor(os.platform, dir, exeName))) {
        return {
          status: 'installed',
          reason: `Steam found at ${dir} (via ${c.label}).`,
          steamDir: dir,
          detectedVia: c.label,
        };
      }
    }

    const where =
      os.platform === 'win32'
        ? `Checked: ${checked.join('; ')}.`
        : 'Steam detection needs Windows — registry and Program Files locations are unavailable on this platform.';
    return {
      status: 'unavailable',
      reason: `Steam not found. ${where}`,
      steamDir: null,
      detectedVia: null,
    };
  }

  /**
   * Discover installed Steam games. Side-effect-free local reads only.
   * Bounded (manifest count + file size) and cancellable via token.
   */
  scan(token?: { cancelled: boolean }): ScanResult {
    const os = this.os;
    const scannedAt = new Date().toISOString();
    const probe = this.probe();
    if (probe.status !== 'installed' || !probe.steamDir) {
      return { status: 'failed', games: [], warnings: [], error: probe.reason, scannedAt };
    }
    const steamDir = probe.steamDir;
    const warnings: string[] = [];
    const games: DiscoveredGame[] = [];
    const seenAppIds = new Set<string>();

    // Library folders: steamapps/libraryfolders.vdf, plus Steam's own dir.
    const folders: string[] = [steamDir];
    const lfPath = joinFor(os.platform, steamDir, 'steamapps', 'libraryfolders.vdf');
    try {
      const text = os.readTextFile(lfPath, MAX_MANIFEST_BYTES);
      const parsed = parseVdf(text);
      if (!parsed.ok) {
        warnings.push(`Could not parse libraryfolders.vdf (${parsed.error.code}); using the Steam install dir only.`);
      } else {
        const lf = parseLibraryFolders(parsed.value);
        warnings.push(...lf.warnings);
        for (const f of lf.folders) {
          if (!folders.some((x) => samePath(os.platform, x, f))) folders.push(f);
        }
      }
    } catch (err) {
      warnings.push(
        `libraryfolders.vdf unreadable (${err instanceof SteamFsError ? err.code : 'error'}); using the Steam install dir only.`,
      );
    }

    let manifestCount = 0;
    for (const folder of folders) {
      const steamapps = joinFor(os.platform, folder, 'steamapps');
      let names: string[];
      try {
        names = os.listDirNames(steamapps);
      } catch {
        warnings.push(`Could not list ${steamapps}; skipped.`);
        continue;
      }
      for (const name of names) {
        if (token?.cancelled) {
          return { status: 'cancelled', games, warnings, error: null, scannedAt };
        }
        const m = MANIFEST_RE.exec(name);
        if (!m) continue;
        const fileAppId = m[1]!;
        if (seenAppIds.has(fileAppId)) {
          warnings.push(`Duplicate manifest for AppID ${fileAppId}; kept the first.`);
          continue;
        }
        if (++manifestCount > MAX_MANIFESTS) {
          warnings.push(`More than ${MAX_MANIFESTS} manifests; remaining ones skipped.`);
          return { status: 'completed', games, warnings, error: null, scannedAt };
        }
        const acfPath = joinFor(os.platform, steamapps, name);
        let text: string;
        try {
          text = os.readTextFile(acfPath, MAX_MANIFEST_BYTES);
        } catch (err) {
          warnings.push(
            `Skipped unreadable manifest ${name} (${err instanceof SteamFsError ? err.code : 'error'}).`,
          );
          continue;
        }
        const parsed = parseVdf(text);
        if (!parsed.ok) {
          warnings.push(`Skipped malformed manifest ${name} (${parsed.error.code}).`);
          continue;
        }
        const manifest = parseAppManifest(parsed.value, fileAppId);
        if (!manifest.ok) {
          warnings.push(`Skipped manifest ${name}: ${manifest.error}`);
          continue;
        }
        warnings.push(...manifest.warnings.map((w) => `${name}: ${w}`));
        seenAppIds.add(fileAppId);
        const installDir = joinFor(os.platform, steamapps, 'common', manifest.manifest.installdir);
        games.push({
          appid: fileAppId,
          title: manifest.manifest.name,
          installDir,
          present: os.isDirectory(installDir),
        });
      }
    }
    return { status: 'completed', games, warnings, error: null, scannedAt };
  }

  /** Classify what launching this AppID can do. No side effects. */
  validateLaunch(appid: string | null): LaunchValidation {
    if (!isValidAppId(appid)) {
      return {
        capability: 'unavailable',
        uri: null,
        reason: `AppID "${appid ?? 'none'}" is not a valid decimal Steam AppID; refusing to build a launch URI.`,
      };
    }
    return {
      capability: 'native-uri',
      uri: buildRunGameUri(appid),
      reason: 'Launches through the installed Steam client via its documented rungameid protocol.',
    };
  }
}

function samePath(platform: NodeJS.Platform, a: string, b: string): boolean {
  if (platform === 'win32') return a.toLowerCase() === b.toLowerCase();
  return a === b;
}
