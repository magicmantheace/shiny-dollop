/**
 * WindowsOsLayer — real implementations against DOCUMENTED Windows APIs.
 *
 * This code is expected to run only on Windows. On any other platform every
 * capability probes as unsupported and every mutating call throws
 * OsLayerError('unsupported') before touching anything — the engine skips
 * unsupported changes, so nothing here can execute accidentally on Linux.
 *
 * Documented APIs used (no private/undocumented calls):
 * - Game Mode:            HKCU\Software\Microsoft\GameBar\AllowAutoGameMode (REG_DWORD),
 *                         read/written with the documented `reg.exe` tool.
 * - Power plan:           `powercfg /getactivescheme` to read,
 *                         `powercfg /setactive <GUID>` to apply.
 * - Process priority:     `tasklist` to find the process by image name;
 *                         .NET `System.Diagnostics.Process.PriorityClass`
 *                         (via powershell.exe) to set it. Only AboveNormal/High.
 *                         Image names must be literal (wildcard syntax is
 *                         rejected — Get-Process -Name would expand it onto
 *                         protected processes), the denylist is re-checked
 *                         against every resolved process, and reads/sets
 *                         address ONE instance by process id so other
 *                         instances' priorities are never touched.
 * - Fullscreen optim.:    per-game values GameDVR_DXGIHonorFSEWindowsCompatible
 *                         and GameDVR_FSEBehaviorMode under
 *                         HKCU\System\GameConfigStore\Children\<game-key>.
 */

import { execFile } from 'node:child_process';
import type { Capability, ChangeKind } from '../../../shared/gpp-types.js';
import {
  AllowedPriority,
  assertValidProcessImageName,
  isDeniedSystemProcess,
  normalizeEnabled,
  normalizeGuid,
  normalizePriority,
  OsLayer,
  OsLayerError,
} from './types.js';

const GAMEBAR_KEY = 'HKCU\\Software\\Microsoft\\GameBar';
const GAMEBAR_VALUE = 'AllowAutoGameMode';
const GAMECONFIG_CHILDREN = 'HKCU\\System\\GameConfigStore\\Children';
const FSE_VALUE_HONOR = 'GameDVR_DXGIHonorFSEWindowsCompatible';
const FSE_VALUE_BEHAVIOR = 'GameDVR_FSEBehaviorMode';

/** FSEBehaviorMode=2 + DXGIHonor=0 disables fullscreen optimizations per game. */
const FSE_DISABLED = { behavior: 2, honor: 0 };
const FSE_ENABLED = { behavior: 0, honor: 1 };

/** Allow only safe registry subkey characters — defense in depth on top of execFile argv. */
const CHILD_KEY_RE = /^[A-Za-z0-9\-_{}.]{1,64}$/;

function validateChildKey(raw: string): string {
  const key = raw.trim();
  if (!CHILD_KEY_RE.test(key)) {
    throw new OsLayerError('refused', `Invalid fullscreen-optimizations childKey "${raw}".`);
  }
  return key;
}

function run(cmd: string, args: string[], timeoutMs = 15000): Promise<string> {
  return new Promise((resolve, reject) => {
    execFile(cmd, args, { timeout: timeoutMs, windowsHide: true }, (err, stdout, stderr) => {
      if (err) {
        reject(new OsLayerError('os-error', `"${cmd}" failed: ${stderr || err.message}`, { cause: err }));
        return;
      }
      resolve(stdout);
    });
  });
}

function parseRegDword(output: string, valueName: string): string | undefined {
  // reg.exe prints e.g.: AllowAutoGameMode    REG_DWORD    0x1
  const re = new RegExp(`${valueName}\\s+REG_DWORD\\s+0x([0-9a-fA-F]+)`);
  const m = re.exec(output);
  return m?.[1];
}

export class WindowsOsLayer implements OsLayer {
  readonly platform = 'win32' as const;

  /** Cached probe results; apply() refuses anything probed unsupported. */
  private capabilitiesCache: Capability[] | undefined;

  private requireWin32(): void {
    if (process.platform !== 'win32') {
      throw new OsLayerError(
        'unsupported',
        'WindowsOsLayer requires Windows; refusing to run OS commands on this platform.',
      );
    }
  }

  private async capabilities(): Promise<Map<string, Capability>> {
    if (!this.capabilitiesCache) {
      this.capabilitiesCache = await this.probeCapabilities();
    }
    return new Map(this.capabilitiesCache.map((c) => [c.id, c]));
  }

  /** Never attempt a change whose capability reports unsupported. */
  private async requireSupported(kind: ChangeKind): Promise<void> {
    this.requireWin32();
    const cap = (await this.capabilities()).get(kind);
    if (!cap?.supported) {
      throw new OsLayerError(
        'unsupported',
        `Capability "${kind}" is unsupported (${cap?.reason ?? 'unknown reason'}) — refusing to attempt.`,
      );
    }
  }

  async probeCapabilities(): Promise<Capability[]> {
    const results: Capability[] = [];
    // game-mode: can we read the GameBar key?
    try {
      await this.readGameModeRaw();
      results.push({
        id: 'game-mode',
        name: 'Game Mode',
        description: 'Toggles Windows Auto Game Mode (HKCU\\Software\\Microsoft\\GameBar).',
        supported: true,
      });
    } catch (e) {
      results.push({
        id: 'game-mode',
        name: 'Game Mode',
        description: 'Toggles Windows Auto Game Mode (HKCU\\Software\\Microsoft\\GameBar).',
        supported: false,
        reason: reasonOf(e),
      });
    }
    // power-plan: does powercfg respond?
    try {
      await this.readPowerPlanRaw();
      results.push({
        id: 'power-plan',
        name: 'Power plan',
        description: 'Switches the active power scheme via powercfg.',
        supported: true,
      });
    } catch (e) {
      results.push({
        id: 'power-plan',
        name: 'Power plan',
        description: 'Switches the active power scheme via powercfg.',
        supported: false,
        reason: reasonOf(e),
      });
    }
    // process-priority: does tasklist respond?
    try {
      await run('tasklist.exe', ['/FO', 'CSV', '/NH']);
      results.push({
        id: 'process-priority',
        name: 'Process priority',
        description: 'Sets a game process priority class (above-normal or high only).',
        supported: true,
      });
    } catch (e) {
      results.push({
        id: 'process-priority',
        name: 'Process priority',
        description: 'Sets a game process priority class (above-normal or high only).',
        supported: false,
        reason: reasonOf(e),
      });
    }
    // fullscreen-optimizations: is the GameConfigStore key readable?
    try {
      await run('reg', ['query', GAMECONFIG_CHILDREN]);
      results.push({
        id: 'fullscreen-optimizations',
        name: 'Fullscreen optimizations',
        description: 'Per-game fullscreen-optimization values under GameConfigStore.',
        supported: true,
      });
    } catch (e) {
      results.push({
        id: 'fullscreen-optimizations',
        name: 'Fullscreen optimizations',
        description: 'Per-game fullscreen-optimization values under GameConfigStore.',
        supported: false,
        reason: reasonOf(e),
      });
    }
    return results;
  }

  async readCurrent(kind: ChangeKind, params: Record<string, string>): Promise<string> {
    this.requireWin32();
    switch (kind) {
      case 'game-mode':
        return (await this.readGameModeRaw()) ? 'enabled' : 'disabled';
      case 'power-plan':
        return this.readPowerPlanRaw();
      case 'process-priority': {
        const image = (params['imageName'] ?? '').trim();
        assertValidProcessImageName(image);
        return this.readPriorityRaw(image);
      }
      case 'fullscreen-optimizations': {
        const key = validateChildKey(params['childKey'] ?? '');
        return this.readFullscreenRaw(key);
      }
    }
  }

  async apply(kind: ChangeKind, params: Record<string, string>): Promise<void> {
    await this.requireSupported(kind);
    switch (kind) {
      case 'game-mode': {
        const enabled = normalizeEnabled(params['enabled']);
        await run('reg', [
          'add', GAMEBAR_KEY,
          '/v', GAMEBAR_VALUE, '/t', 'REG_DWORD', '/d', enabled ? '1' : '0', '/f',
        ]);
        return;
      }
      case 'power-plan': {
        const guid = normalizeGuid(params['guid'] ?? '');
        await run('powercfg.exe', ['/setactive', guid]);
        return;
      }
      case 'process-priority': {
        const image = (params['imageName'] ?? '').trim();
        assertValidProcessImageName(image);
        const priority = normalizePriority(params['priority'] ?? '');
        await this.setPriorityRaw(image, priority);
        return;
      }
      case 'fullscreen-optimizations': {
        const key = validateChildKey(params['childKey'] ?? '');
        const disabled = normalizeEnabled(params['disableFse']);
        const vals = disabled ? FSE_DISABLED : FSE_ENABLED;
        const fullKey = `${GAMECONFIG_CHILDREN}\\${key}`;
        await run('reg', ['add', fullKey, '/v', FSE_VALUE_BEHAVIOR, '/t', 'REG_DWORD', '/d', String(vals.behavior), '/f']);
        await run('reg', ['add', fullKey, '/v', FSE_VALUE_HONOR, '/t', 'REG_DWORD', '/d', String(vals.honor), '/f']);
        return;
      }
    }
  }

  async restore(kind: ChangeKind, params: Record<string, string>, value: string): Promise<void> {
    this.requireWin32();
    switch (kind) {
      case 'game-mode': {
        if (value !== 'enabled' && value !== 'disabled') {
          throw new OsLayerError('refused', `Cannot restore game-mode to unknown value "${value}".`);
        }
        await this.apply(kind, { ...params, enabled: value === 'enabled' ? 'true' : 'false' });
        return;
      }
      case 'power-plan':
        await this.apply(kind, { ...params, guid: value });
        return;
      case 'process-priority': {
        const image = (params['imageName'] ?? '').trim();
        assertValidProcessImageName(image);
        const restored = restorePriorityFromString(value);
        await this.setPriorityRaw(image, restored);
        return;
      }
      case 'fullscreen-optimizations': {
        const key = validateChildKey(params['childKey'] ?? '');
        const disabled = value === 'disabled';
        if (!disabled && value !== 'enabled') {
          throw new OsLayerError('refused', `Cannot restore fullscreen-optimizations to unknown value "${value}".`);
        }
        const vals = disabled ? FSE_DISABLED : FSE_ENABLED;
        const fullKey = `${GAMECONFIG_CHILDREN}\\${key}`;
        await run('reg', ['add', fullKey, '/v', FSE_VALUE_BEHAVIOR, '/t', 'REG_DWORD', '/d', String(vals.behavior), '/f']);
        await run('reg', ['add', fullKey, '/v', FSE_VALUE_HONOR, '/t', 'REG_DWORD', '/d', String(vals.honor), '/f']);
        return;
      }
    }
  }

  async takeSnapshot(): Promise<{ cpuPercent: number; memoryMb: number }> {
    this.requireWin32();
    // Best-effort point-in-time estimate via documented tools.
    // typeperf counters are sampled once; failure yields a clearly-marked fallback.
    try {
      const out = await run('powershell.exe', [
        '-NoProfile', '-NonInteractive', '-Command',
        "$c=(Get-Counter '\\Processor(_Total)\\% Processor Time').CounterSamples[0].CookedValue;" +
          "$m=(Get-Counter '\\Memory\\Available MBytes').CounterSamples[0].CookedValue;" +
          "$t=(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory/1MB;" +
          "\"$([math]::Round($c,1)) $([math]::Round($t-$m,0))\"",
      ]);
      const parts = out.trim().split(/\s+/);
      const cpu = Number(parts[0]);
      const mem = Number(parts[1]);
      if (Number.isFinite(cpu) && Number.isFinite(mem)) {
        return { cpuPercent: cpu, memoryMb: mem };
      }
    } catch {
      // fall through to fallback
    }
    return { cpuPercent: -1, memoryMb: -1 }; // counters unavailable; still labelled approximate
  }

  // -- raw helpers ----------------------------------------------------------

  private async readGameModeRaw(): Promise<boolean> {
    this.requireWin32();
    const out = await run('reg', ['query', GAMEBAR_KEY, '/v', GAMEBAR_VALUE]);
    const hex = parseRegDword(out, GAMEBAR_VALUE);
    return hex !== undefined && parseInt(hex, 16) !== 0;
  }

  private async readPowerPlanRaw(): Promise<string> {
    this.requireWin32();
    // powercfg prints: Power Scheme GUID: 381b4222-...  (Balanced)
    const out = await run('powercfg.exe', ['/getactivescheme']);
    const m = /([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})/.exec(out);
    if (!m?.[1]) throw new OsLayerError('os-error', 'Could not parse powercfg /getactivescheme output.');
    return m[1].toLowerCase();
  }

  /**
   * Resolve every running instance of the (already wildcard-validated,
   * literal) image name to its identity: id, process name, priority class.
   * Resolution is a read — nothing is mutated here.
   */
  private async resolveProcessesRaw(imageName: string): Promise<ResolvedProcess[]> {
    this.requireWin32();
    const out = await run('powershell.exe', [
      '-NoProfile', '-NonInteractive', '-Command',
      `$ps=Get-Process -Name '${psEscape(baseName(imageName))}' -ErrorAction SilentlyContinue;` +
        'if (-not $ps) { throw "not-found" };' +
        '$ps | ForEach-Object { "$($_.Id)|$($_.ProcessName)|$($_.PriorityClass.ToString())" }',
    ]).catch((e) => {
      if (/not-found/.test(String(e))) {
        throw new OsLayerError('not-found', `Process "${imageName}" is not running.`);
      }
      throw e;
    });
    const procs = parseResolvedProcesses(out);
    if (procs.length === 0) {
      throw new OsLayerError('not-found', `Process "${imageName}" is not running.`);
    }
    return procs;
  }

  private async readPriorityRaw(imageName: string): Promise<string> {
    // Single-instance contract (shared with setPriorityRaw): the FIRST
    // resolved instance is the one whose priority is recorded — and the
    // only one a later set/restore will ever touch — so other instances'
    // original priorities are never read, changed, or overwritten.
    const [first] = await this.resolveProcessesRaw(imageName);
    return normalizePriorityClassName(first!.priorityClass);
  }

  private async setPriorityRaw(imageName: string, priority: AllowedPriority | RestorePriority): Promise<void> {
    this.requireWin32();
    const procs = await this.resolveProcessesRaw(imageName);
    // Enforce the denylist against every RESOLVED process before any
    // mutation — the requested name was validated as a literal, and this
    // closes the loop on what the OS actually matched.
    assertNoResolvedProcessDenied(procs);
    // Mutate exactly the same single instance readPriorityRaw records,
    // addressed by process id — never every instance sharing the name.
    const target = procs[0]!;
    const psClass = priorityClassName(priority);
    await run('powershell.exe', [
      '-NoProfile', '-NonInteractive', '-Command',
      buildSetPriorityByIdScript(target.id, psClass),
    ]).catch((e) => {
      if (/not-found/.test(String(e))) {
        throw new OsLayerError('not-found', `Process "${imageName}" is not running.`);
      }
      throw e;
    });
  }

  private async readFullscreenRaw(childKey: string): Promise<string> {
    this.requireWin32();
    try {
      const out = await run('reg', ['query', `${GAMECONFIG_CHILDREN}\\${childKey}`]);
      const behavior = parseRegDword(out, FSE_VALUE_BEHAVIOR);
      const honor = parseRegDword(out, FSE_VALUE_HONOR);
      const disabled =
        (behavior !== undefined && parseInt(behavior, 16) === FSE_DISABLED.behavior) ||
        (honor !== undefined && parseInt(honor, 16) === FSE_DISABLED.honor);
      return disabled ? 'disabled' : 'enabled';
    } catch (e) {
      if (/The system was unable to find the specified registry key/.test(String(e))) {
        return 'enabled'; // no per-game override: OS default (optimizations on)
      }
      throw e;
    }
  }
}

function reasonOf(e: unknown): string {
  if (e instanceof OsLayerError) return e.message;
  return e instanceof Error ? e.message : String(e);
}

function baseName(imageName: string): string {
  return imageName.replace(/\.exe$/i, '');
}

function psEscape(s: string): string {
  return s.replace(/'/g, "''");
}

/** Canonical .NET ProcessPriorityClass name; realtime is unreachable by construction. */
function priorityClassName(p: AllowedPriority | RestorePriority): string {
  switch (p) {
    case 'Idle': return 'Idle';
    case 'BelowNormal': return 'BelowNormal';
    case 'Normal': return 'Normal';
    case 'AboveNormal': return 'AboveNormal';
    case 'High': return 'High';
    case 'above-normal': return 'AboveNormal';
    case 'high': return 'High';
  }
}

/**
 * Map a journaled `before` value back to a real priority class for restore.
 * Restore may set any non-realtime class — it is returning the process to its
 * exact recorded prior state, which is always safe. Unknown values and any
 * realtime request fall back to Normal. Realtime is never set.
 */
type RestorePriority = 'Idle' | 'BelowNormal' | 'Normal' | 'AboveNormal' | 'High';

function restorePriorityFromString(value: string): RestorePriority {
  const v = value.trim().toLowerCase();
  if (v === 'high') return 'High';
  if (v === 'above-normal' || v === 'abovenormal') return 'AboveNormal';
  if (v === 'below-normal' || v === 'belownormal') return 'BelowNormal';
  if (v === 'idle') return 'Idle';
  return 'Normal';
}

// -- resolved-process helpers (pure; exported for tests) --------------------

/** One running process instance, as resolved by resolveProcessesRaw(). */
export interface ResolvedProcess {
  id: number;
  processName: string;
  priorityClass: string;
}

/** Parse `id|processName|priorityClass` lines; blank/garbage lines are ignored. */
export function parseResolvedProcesses(output: string): ResolvedProcess[] {
  const procs: ResolvedProcess[] = [];
  for (const line of output.split(/\r?\n/)) {
    const m = /^(\d+)\|([^|]+)\|([A-Za-z]+)$/.exec(line.trim());
    if (m) {
      procs.push({ id: Number(m[1]), processName: m[2]!, priorityClass: m[3]! });
    }
  }
  return procs;
}

/**
 * Refuse (before any mutation) when ANY resolved process is on the
 * system-process denylist. Get-Process returns process names without the
 * `.exe` suffix, so both forms are checked via isDeniedSystemProcess.
 */
export function assertNoResolvedProcessDenied(procs: readonly ResolvedProcess[]): void {
  for (const p of procs) {
    if (isDeniedSystemProcess(p.processName) || isDeniedSystemProcess(`${p.processName}.exe`)) {
      throw new OsLayerError(
        'refused',
        `Refusing to change priority of system process "${p.processName}" (resolved process id ${p.id}).`,
      );
    }
  }
}

/** 'AboveNormal' -> 'above-normal', 'Normal' -> 'normal', etc. */
export function normalizePriorityClassName(raw: string): string {
  return raw.trim().replace(/([a-z])([A-Z])/g, '$1-$2').toLowerCase();
}

/**
 * PowerShell that sets the priority of exactly ONE process, addressed by
 * id — the same instance readPriorityRaw recorded. Setting by id (rather
 * than re-querying by name and touching every match) is what keeps other
 * instances' original priorities intact across an activate/rollback cycle.
 */
export function buildSetPriorityByIdScript(id: number, psClass: string): string {
  if (!Number.isInteger(id) || id <= 0) {
    throw new OsLayerError('refused', `Invalid process id "${id}".`);
  }
  return (
    `$p=Get-Process -Id ${id} -ErrorAction SilentlyContinue;` +
    'if (-not $p) { throw "not-found" };' +
    `$p.PriorityClass = [System.Diagnostics.ProcessPriorityClass]::${psClass}`
  );
}
