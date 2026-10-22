/**
 * Battle.net source adapter.
 *
 * Honest best-effort design (see docs/BATTLENET_INVESTIGATION.md): per-game
 * discovery is NOT reliably possible from local non-secret metadata, so this
 * adapter detects the client and offers an explicit "Open Battle.net" action.
 * It never invents product IDs, deep links, or game entries.
 *
 * Adapter contract notes:
 * - probe() → installed/unavailable + reason (client exe located or not).
 * - scan() → always completes with zero games and an explanatory warning;
 *   a source with no discovery mechanism must not fail the whole scan.
 * - validateLaunch()/launch() are per-game and therefore unavailable for
 *   this source; the client itself is opened via GameLauncher.openClient().
 */
import { joinFor, type BattleNetOs } from './os';

export type ProbeStatus = 'installed' | 'unavailable';

export interface ProbeResult {
  status: ProbeStatus;
  /** Human-readable reason, including the detection method and paths checked. */
  reason: string;
  /** Validated absolute path of Battle.net.exe when found. */
  clientExe: string | null;
  /** Which candidate located the client. */
  detectedVia: string | null;
}

export interface ScanResult {
  status: 'completed';
  warnings: string[];
  scannedAt: string;
}

const CLIENT_EXE = 'Battle.net.exe';

const NO_DISCOVERY_WARNING =
  'Per-game Battle.net discovery is not supported: no documented local metadata ' +
  'reliably identifies installed Blizzard games (see docs/BATTLENET_INVESTIGATION.md). ' +
  'Add Battle.net games with Add Game, or open the client from Settings.';

export class BattleNetAdapter {
  constructor(private readonly os: BattleNetOs) {}

  /**
   * Locate the Battle.net client executable in well-known install locations.
   * Read-only; never writes anything.
   */
  probe(): ProbeResult {
    const os = this.os;
    const candidates: Array<{ dir: string | undefined; label: string }> = [
      { dir: joinFor(os.platform, os.env('ProgramFiles(x86)') ?? '', 'Battle.net'), label: '%ProgramFiles(x86)%\\Battle.net' },
      { dir: joinFor(os.platform, os.env('ProgramFiles') ?? '', 'Battle.net'), label: '%ProgramFiles%\\Battle.net' },
    ];
    const checked: string[] = [];
    for (const c of candidates) {
      if (!c.dir) continue;
      checked.push(c.label);
      const exe = joinFor(os.platform, c.dir, CLIENT_EXE);
      if (os.isFile(exe)) {
        return {
          status: 'installed',
          reason: `Battle.net client found at ${exe} (via ${c.label}). ${NO_DISCOVERY_WARNING}`,
          clientExe: exe,
          detectedVia: c.label,
        };
      }
    }
    const where =
      os.platform === 'win32'
        ? `Checked: ${checked.join('; ')}.`
        : 'Battle.net detection needs Windows — Program Files locations are unavailable on this platform.';
    return {
      status: 'unavailable',
      reason: `Battle.net client not found. ${where}`,
      clientExe: null,
      detectedVia: null,
    };
  }

  /**
   * No per-game discovery exists; report that honestly. Completing (rather
   * than failing) keeps one unsupported source from breaking a whole scan.
   */
  scan(): ScanResult {
    const probe = this.probe();
    const warnings =
      probe.status === 'installed'
        ? [NO_DISCOVERY_WARNING]
        : [`Scan skipped: ${probe.reason}`];
    return { status: 'completed', warnings, scannedAt: new Date().toISOString() };
  }
}
