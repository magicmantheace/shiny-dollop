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
 *                         instances' priorities are never touched. The
 *                         selected instance's identity (process id +
 *                         creation-time ticks) is retained as recovery
 *                         state at apply() time; restore() re-targets
 *                         exactly that identity and touches NOTHING when
 *                         the original instance has exited (or its pid has
 *                         been reused), instead of re-resolving the image
 *                         name onto a surviving replacement instance.
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

  /**
   * Process-priority recovery state: for each image name, the stack of
   * instances apply() actually mutated (identity + the priority recorded
   * just before the mutation). restore() consumes the matching entry and
   * re-targets that exact instance — never a same-name replacement.
   */
  private priorityRecovery = new PriorityRecoveryLog();

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
        await this.applyPriorityRaw(image, priority);
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
        await this.restorePriorityRaw(image, restored);
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
   * literal) image name to its identity: id, process name, priority class,
   * and creation-time ticks (0 when StartTime is not readable for that
   * instance — identity then degrades to the process id alone).
   * Resolution is a read — nothing is mutated here.
   */
  private async resolveProcessesRaw(imageName: string): Promise<ResolvedProcess[]> {
    this.requireWin32();
    const out = await run('powershell.exe', [
      '-NoProfile', '-NonInteractive', '-Command',
      `$ps=Get-Process -Name '${psEscape(baseName(imageName))}' -ErrorAction SilentlyContinue;` +
        'if (-not $ps) { throw "not-found" };' +
        '$ps | ForEach-Object { $t=0; try { $t=$_.StartTime.ToUniversalTime().Ticks } catch {}; ' +
        '"$($_.Id)|$($_.ProcessName)|$($_.PriorityClass.ToString())|$t" }',
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
    // Single-instance contract (shared with applyPriorityRaw): the FIRST
    // resolved instance is the one whose priority is recorded — and the
    // only one a later set/restore will ever touch — so other instances'
    // original priorities are never read, changed, or overwritten.
    const [first] = await this.resolveProcessesRaw(imageName);
    return normalizePriorityClassName(first!.priorityClass);
  }

  /**
   * Apply path: resolve ONCE, retain the selected instance's identity and
   * its pre-change priority as recovery state, then mutate exactly that
   * instance (identity-verified again inside the set script).
   */
  private async applyPriorityRaw(imageName: string, priority: AllowedPriority): Promise<void> {
    this.requireWin32();
    const procs = await this.resolveProcessesRaw(imageName);
    // Enforce the denylist against every RESOLVED process before any
    // mutation — the requested name was validated as a literal, and this
    // closes the loop on what the OS actually matched.
    assertNoResolvedProcessDenied(procs);
    // Mutate exactly the same single instance readPriorityRaw records,
    // addressed by process id — never every instance sharing the name.
    const target = procs[0]!;
    const before = normalizePriorityClassName(target.priorityClass);
    await this.setPriorityOnInstance(imageName, target, priority);
    // Record recovery state only after the mutation succeeded: restore()
    // must be able to find (and only ever touch) this exact instance.
    this.priorityRecovery.record(imageName, identityOf(target), before);
  }

  /**
   * Restore path: re-target the instance apply() selected, via the
   * retained recovery identity — NOT a fresh name resolution. When the
   * original instance has exited (or its pid was reused by a process with
   * a different creation time), restore is a successful no-op: there is
   * nothing left to restore, and writing the recorded priority onto a
   * surviving same-name instance would corrupt a process this app never
   * changed. Without retained identity (e.g. a journal entry written
   * before this session), restore proceeds only when exactly ONE instance
   * matches — with several, it refuses rather than guessing.
   */
  private async restorePriorityRaw(imageName: string, priority: RestorePriority): Promise<void> {
    this.requireWin32();
    const beforeKey = normalizePriorityClassName(priorityClassName(priority));
    // Peek, don't consume yet: if the set below fails, the entry must stay
    // so a retry still targets the recorded instance instead of degrading
    // to a name-based guess.
    const identity = this.priorityRecovery.find(imageName, beforeKey);
    let procs: ResolvedProcess[];
    try {
      procs = await this.resolveProcessesRaw(imageName);
    } catch (e) {
      // With a retained identity, "no instances running" just means the
      // original is gone — nothing to restore, nothing to touch.
      if (identity && e instanceof OsLayerError && e.code === 'not-found') {
        this.priorityRecovery.consume(imageName, beforeKey);
        return;
      }
      throw e;
    }
    assertNoResolvedProcessDenied(procs);
    const plan = planPriorityRestore(procs, identity);
    switch (plan.action) {
      case 'gone':
        this.priorityRecovery.consume(imageName, beforeKey);
        return; // original instance exited / pid reused: touch nothing
      case 'ambiguous':
        throw new OsLayerError(
          'refused',
          `Refusing to restore priority for "${imageName}": ${procs.length} instances are running ` +
            'and the instance originally changed is not recorded in this session, so restoring ' +
            'could modify the wrong instance. The journal entry was left in place.',
        );
      case 'set':
        await this.setPriorityOnInstance(imageName, plan.target, priority);
        this.priorityRecovery.consume(imageName, beforeKey);
        return;
    }
  }

  /** Set one already-resolved instance's priority, verifying its identity in the set script itself. */
  private async setPriorityOnInstance(
    imageName: string,
    target: ResolvedProcess,
    priority: AllowedPriority | RestorePriority,
  ): Promise<void> {
    const psClass = priorityClassName(priority);
    await run('powershell.exe', [
      '-NoProfile', '-NonInteractive', '-Command',
      buildSetPriorityByIdentityScript(target, psClass),
    ]).catch((e) => {
      if (/not-found|identity-changed/.test(String(e))) {
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
  /**
   * Process creation time as .NET DateTime ticks (string: the value
   * exceeds Number.MAX_SAFE_INTEGER), or '0'/absent when StartTime was
   * not readable. Together with `id` this is the instance's identity:
   * a reused pid has a different creation time.
   */
  startTimeTicks?: string;
}

/** Parse `id|processName|priorityClass[|startTimeTicks]` lines; blank/garbage lines are ignored. */
export function parseResolvedProcesses(output: string): ResolvedProcess[] {
  const procs: ResolvedProcess[] = [];
  for (const line of output.split(/\r?\n/)) {
    const m = /^(\d+)\|([^|]+)\|([A-Za-z]+)(?:\|(\d+))?$/.exec(line.trim());
    if (m) {
      procs.push({
        id: Number(m[1]),
        processName: m[2]!,
        priorityClass: m[3]!,
        ...(m[4] !== undefined ? { startTimeTicks: m[4] } : {}),
      });
    }
  }
  return procs;
}

/** The identity of one process instance: pid + creation time. */
export interface ProcessIdentity {
  id: number;
  startTimeTicks?: string;
}

export function identityOf(proc: ResolvedProcess): ProcessIdentity {
  return {
    id: proc.id,
    ...(proc.startTimeTicks !== undefined ? { startTimeTicks: proc.startTimeTicks } : {}),
  };
}

/** True when ticks carry real creation-time information ('0' = unreadable). */
function ticksKnown(ticks: string | undefined): ticks is string {
  return ticks !== undefined && ticks !== '0';
}

/**
 * Decide what a priority restore may touch.
 *
 * - With a retained identity: `set` only the exact instance (same pid AND,
 *   when both are known, same creation ticks). A pid whose creation ticks
 *   differ is a DIFFERENT process that reused the pid — that, like a pid
 *   that no longer exists, is `gone`: the original instance exited and no
 *   surviving instance may be modified in its place.
 * - Without a retained identity: `set` only when exactly one instance is
 *   running (unambiguous); with several, `ambiguous` — the caller refuses
 *   rather than guessing which instance the journal entry belongs to.
 */
export type PriorityRestorePlan =
  | { action: 'set'; target: ResolvedProcess }
  | { action: 'gone' }
  | { action: 'ambiguous' };

export function planPriorityRestore(
  procs: readonly ResolvedProcess[],
  identity: ProcessIdentity | undefined,
): PriorityRestorePlan {
  if (identity) {
    const match = procs.find((p) => p.id === identity.id);
    if (!match) return { action: 'gone' };
    if (
      ticksKnown(identity.startTimeTicks) &&
      ticksKnown(match.startTimeTicks) &&
      match.startTimeTicks !== identity.startTimeTicks
    ) {
      return { action: 'gone' }; // pid reused by a later process
    }
    return { action: 'set', target: match };
  }
  if (procs.length === 1) return { action: 'set', target: procs[0]! };
  return { action: 'ambiguous' };
}

/**
 * Recovery state for process-priority changes: per image name, a stack of
 * { identity, before } entries recorded by apply() for the instance it
 * actually mutated. restore() looks up the entry whose recorded `before`
 * matches the journal value being restored (newest first — rollback
 * unwinds newest first) so stacked activations of the same executable
 * each restore their own instance state.
 */
export class PriorityRecoveryLog {
  private stacks = new Map<string, Array<{ identity: ProcessIdentity; before: string }>>();

  private key(imageName: string): string {
    return imageName.trim().toLowerCase();
  }

  record(imageName: string, identity: ProcessIdentity, before: string): void {
    const k = this.key(imageName);
    const stack = this.stacks.get(k) ?? [];
    stack.push({ identity, before });
    this.stacks.set(k, stack);
  }

  /** Newest retained identity whose recorded before-value matches, or undefined. */
  find(imageName: string, before: string): ProcessIdentity | undefined {
    const stack = this.stacks.get(this.key(imageName));
    if (!stack) return undefined;
    for (let i = stack.length - 1; i >= 0; i--) {
      if (stack[i]!.before === before) return stack[i]!.identity;
    }
    return undefined;
  }

  /** Drop the newest entry matching `before` (after a restore used it). */
  consume(imageName: string, before: string): void {
    const k = this.key(imageName);
    const stack = this.stacks.get(k);
    if (!stack) return;
    for (let i = stack.length - 1; i >= 0; i--) {
      if (stack[i]!.before === before) {
        stack.splice(i, 1);
        break;
      }
    }
    if (stack.length === 0) this.stacks.delete(k);
  }
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

/**
 * Like buildSetPriorityByIdScript, but the script itself re-verifies the
 * instance's creation-time ticks before mutating: if the pid was reused
 * between resolution and this call, it throws "identity-changed" and
 * touches nothing. This closes the exit/reuse race inside the restore
 * path, not just at plan time.
 */
export function buildSetPriorityByIdentityScript(proc: ResolvedProcess, psClass: string): string {
  const base = buildSetPriorityByIdScript(proc.id, psClass);
  if (!ticksKnown(proc.startTimeTicks)) return base;
  if (!/^\d+$/.test(proc.startTimeTicks)) {
    throw new OsLayerError('refused', `Invalid process start-time ticks "${proc.startTimeTicks}".`);
  }
  const verify =
    `if ($p.StartTime.ToUniversalTime().Ticks -ne ${proc.startTimeTicks}) { throw "identity-changed" };`;
  return base.replace(
    'if (-not $p) { throw "not-found" };',
    `if (-not $p) { throw "not-found" };${verify}`,
  );
}
