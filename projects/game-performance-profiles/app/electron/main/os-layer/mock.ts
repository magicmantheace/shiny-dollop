/**
 * MockOsLayer — in-memory OsLayer for tests and non-Windows development.
 *
 * Behaves like the real layer (read/apply/restore round-trips, capability
 * probing, denylist refusal) against synthetic state. Supports failure
 * injection for engine failure-mode tests:
 * - `failOnApplyAt`: throw on the Nth apply() call (1-based).
 * - `unsupportedCapabilities`: capability ids that probe as unsupported;
 *   apply() for those kinds throws OsLayerError('unsupported') and never
 *   mutates state.
 * - `deniedProcesses`: extra image names refused for process-priority,
 *   on top of the built-in SYSTEM_PROCESS_DENYLIST.
 */

import type { Capability, ChangeKind } from '../../../shared/gpp-types.js';
import {
  SYSTEM_PROCESS_DENYLIST,
  assertValidProcessImageName,
  describeDesired,
  normalizeEnabled,
  normalizeGuid,
  normalizePriority,
  OsLayer,
  OsLayerError,
} from './types.js';

export interface MockOsLayerOptions {
  /** Throw on the Nth apply() call (1-based). Useful for mid-activation failures. */
  failOnApplyAt?: number;
  /** Capability ids (change kinds) that probe as unsupported. */
  unsupportedCapabilities?: Set<string>;
  /** Extra process image names refused for process-priority. */
  deniedProcesses?: Set<string>;
  /** Initial synthetic state. */
  initial?: Partial<MockState>;
}

export interface MockState {
  gameModeEnabled: boolean;
  activePowerGuid: string;
  processPriorities: Record<string, string>;
  /** childKey -> 'disabled' | 'enabled' for fullscreen optimizations */
  fullscreenOptimizations: Record<string, string>;
  /** Synthetic telemetry returned by takeSnapshot(). */
  cpuPercent: number;
  memoryMb: number;
}

const DEFAULT_GUID = '381b4222-f694-41f0-9685-ff5bb260df2e'; // Windows "Balanced"

export class MockOsLayer implements OsLayer {
  readonly platform = 'mock' as const;

  private state: MockState = {
    gameModeEnabled: false,
    activePowerGuid: DEFAULT_GUID,
    processPriorities: {},
    fullscreenOptimizations: {},
    cpuPercent: 12.5,
    memoryMb: 8192,
  };

  private applyCount = 0;
  private readonly failOnApplyAt: number | undefined;
  private readonly unsupported: Set<string>;
  private readonly extraDenied: Set<string>;

  constructor(options: MockOsLayerOptions = {}) {
    this.failOnApplyAt = options.failOnApplyAt;
    this.unsupported = options.unsupportedCapabilities ?? new Set();
    this.extraDenied = new Set([...(options.deniedProcesses ?? [])].map((s) => s.toLowerCase()));
    if (options.initial) {
      this.state = { ...this.state, ...options.initial };
      if (options.initial.processPriorities) {
        this.state.processPriorities = { ...options.initial.processPriorities };
      }
      if (options.initial.fullscreenOptimizations) {
        this.state.fullscreenOptimizations = { ...options.initial.fullscreenOptimizations };
      }
    }
  }

  /** Number of apply() calls made so far — useful for "never attempted" assertions. */
  get appliedCalls(): number {
    return this.applyCount;
  }

  /** Read-only view of synthetic state for test assertions. */
  get snapshot(): Readonly<MockState> {
    return {
      ...this.state,
      processPriorities: { ...this.state.processPriorities },
      fullscreenOptimizations: { ...this.state.fullscreenOptimizations },
    };
  }

  async probeCapabilities(): Promise<Capability[]> {
    const defs: Array<{ id: ChangeKind; name: string; description: string }> = [
      {
        id: 'game-mode',
        name: 'Game Mode',
        description: 'Toggles Windows Auto Game Mode (HKCU\\Software\\Microsoft\\GameBar).',
      },
      {
        id: 'power-plan',
        name: 'Power plan',
        description: 'Switches the active power scheme via powercfg.',
      },
      {
        id: 'process-priority',
        name: 'Process priority',
        description: 'Sets a game process priority class (above-normal or high only).',
      },
      {
        id: 'fullscreen-optimizations',
        name: 'Fullscreen optimizations',
        description: 'Per-game fullscreen-optimization values under GameConfigStore.',
      },
    ];
    return defs.map((d) =>
      this.unsupported.has(d.id)
        ? { ...d, supported: false, reason: `Mocked as unsupported: ${d.id}` }
        : { ...d, supported: true },
    );
  }

  async readCurrent(kind: ChangeKind, params: Record<string, string>): Promise<string> {
    switch (kind) {
      case 'game-mode':
        return this.state.gameModeEnabled ? 'enabled' : 'disabled';
      case 'power-plan':
        return this.state.activePowerGuid;
      case 'process-priority': {
        const raw = (params['imageName'] ?? '').trim();
        assertValidProcessImageName(raw);
        const image = raw.toLowerCase();
        return this.state.processPriorities[image] ?? 'normal';
      }
      case 'fullscreen-optimizations': {
        const key = (params['childKey'] ?? '').trim();
        if (!key) throw new OsLayerError('refused', 'fullscreen-optimizations requires params.childKey');
        return this.state.fullscreenOptimizations[key] ?? 'enabled';
      }
    }
  }

  async apply(kind: ChangeKind, params: Record<string, string>): Promise<void> {
    this.applyCount += 1;
    if (this.unsupported.has(kind)) {
      throw new OsLayerError('unsupported', `Capability "${kind}" is unsupported — refusing to attempt.`);
    }
    if (this.failOnApplyAt !== undefined && this.applyCount === this.failOnApplyAt) {
      throw new OsLayerError('os-error', `Injected failure on apply #${this.applyCount} (${kind}).`);
    }
    switch (kind) {
      case 'game-mode': {
        this.state.gameModeEnabled = normalizeEnabled(params['enabled']);
        return;
      }
      case 'power-plan': {
        this.state.activePowerGuid = normalizeGuid(params['guid'] ?? '');
        return;
      }
      case 'process-priority': {
        const image = (params['imageName'] ?? '').trim();
        assertValidProcessImageName(image);
        if (this.extraDenied.has(image.toLowerCase())) {
          throw new OsLayerError(
            'refused',
            `Refusing to change priority of system process "${image}" (denylist: ${SYSTEM_PROCESS_DENYLIST.join(', ')}).`,
          );
        }
        const priority = normalizePriority(params['priority'] ?? '');
        this.state.processPriorities[image.toLowerCase()] = priority;
        return;
      }
      case 'fullscreen-optimizations': {
        const key = (params['childKey'] ?? '').trim();
        if (!key) throw new OsLayerError('refused', 'fullscreen-optimizations requires params.childKey');
        this.state.fullscreenOptimizations[key] = describeDesired(kind, params);
        return;
      }
    }
  }

  async restore(kind: ChangeKind, params: Record<string, string>, value: string): Promise<void> {
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
        if (this.extraDenied.has(image.toLowerCase())) {
          throw new OsLayerError('refused', `Refusing to change priority of system process "${image}".`);
        }
        this.state.processPriorities[image.toLowerCase()] = value;
        return;
      }
      case 'fullscreen-optimizations': {
        const key = (params['childKey'] ?? '').trim();
        if (!key) throw new OsLayerError('refused', 'fullscreen-optimizations requires params.childKey');
        if (value !== 'enabled' && value !== 'disabled') {
          throw new OsLayerError('refused', `Cannot restore fullscreen-optimizations to unknown value "${value}".`);
        }
        this.state.fullscreenOptimizations[key] = value;
        return;
      }
    }
  }

  async takeSnapshot(): Promise<{ cpuPercent: number; memoryMb: number }> {
    return { cpuPercent: this.state.cpuPercent, memoryMb: this.state.memoryMb };
  }
}
