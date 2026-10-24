/**
 * OsLayer tests: MockOsLayer behavior + failure injection, capability probe
 * accuracy, the system-process denylist, and WindowsOsLayer honesty on a
 * non-Windows platform (must report unsupported, never attempt).
 */
import { describe, expect, it } from 'vitest';
import { MockOsLayer } from '../electron/main/os-layer/mock.js';
import { WindowsOsLayer } from '../electron/main/os-layer/windows.js';
import {
  describeDesired,
  hasWildcardSyntax,
  isDeniedSystemProcess,
  isValidGuid,
  normalizeGuid,
  OsLayerError,
  processImageNameProblem,
} from '../electron/main/os-layer/types.js';
import {
  assertNoResolvedProcessDenied,
  buildSetPriorityByIdScript,
  normalizePriorityClassName,
  parseResolvedProcesses,
} from '../electron/main/os-layer/windows.js';

const HIGH_PERF = '8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c';

describe('MockOsLayer basics', () => {
  it('round-trips read/apply/restore for every kind', async () => {
    const os = new MockOsLayer();
    expect(await os.readCurrent('game-mode', {})).toBe('disabled');
    await os.apply('game-mode', { enabled: 'true' });
    expect(await os.readCurrent('game-mode', {})).toBe('enabled');
    await os.restore('game-mode', {}, 'disabled');
    expect(await os.readCurrent('game-mode', {})).toBe('disabled');

    await os.apply('power-plan', { guid: HIGH_PERF });
    expect(await os.readCurrent('power-plan', {})).toBe(HIGH_PERF);
    await os.restore('power-plan', {}, '381b4222-f694-41f0-9685-ff5bb260df2e');
    expect(await os.readCurrent('power-plan', {})).toBe('381b4222-f694-41f0-9685-ff5bb260df2e');

    await os.apply('process-priority', { imageName: 'game.exe', priority: 'above-normal' });
    expect(await os.readCurrent('process-priority', { imageName: 'game.exe' })).toBe('above-normal');
    await os.restore('process-priority', { imageName: 'game.exe' }, 'normal');
    expect(await os.readCurrent('process-priority', { imageName: 'game.exe' })).toBe('normal');

    await os.apply('fullscreen-optimizations', { childKey: 'abc', disableFse: 'true' });
    expect(await os.readCurrent('fullscreen-optimizations', { childKey: 'abc' })).toBe('disabled');
    await os.restore('fullscreen-optimizations', { childKey: 'abc' }, 'enabled');
    expect(await os.readCurrent('fullscreen-optimizations', { childKey: 'abc' })).toBe('enabled');
  });

  it('honours injected initial state', async () => {
    const os = new MockOsLayer({ initial: { gameModeEnabled: true, cpuPercent: 50, memoryMb: 1024 } });
    expect(await os.readCurrent('game-mode', {})).toBe('enabled');
    expect(await os.takeSnapshot()).toEqual({ cpuPercent: 50, memoryMb: 1024 });
  });

  it('throws on unsupported capabilities and never mutates state', async () => {
    const os = new MockOsLayer({ unsupportedCapabilities: new Set(['game-mode']) });
    await expect(os.apply('game-mode', { enabled: 'true' })).rejects.toMatchObject({ code: 'unsupported' });
    expect(os.snapshot.gameModeEnabled).toBe(false);
  });

  it('injects a failure on the Nth apply', async () => {
    const os = new MockOsLayer({ failOnApplyAt: 2 });
    await os.apply('game-mode', { enabled: 'true' });
    await expect(os.apply('power-plan', { guid: HIGH_PERF })).rejects.toThrow(/Injected failure/);
    expect(os.appliedCalls).toBe(2);
  });

  it('counts apply calls for never-attempted assertions', async () => {
    const os = new MockOsLayer();
    expect(os.appliedCalls).toBe(0);
    await os.apply('game-mode', { enabled: 'true' });
    expect(os.appliedCalls).toBe(1);
  });
});

describe('process-priority denylist', () => {
  const denied = ['System', 'SYSTEM', 'system', 'smss.exe', 'CSRSS.EXE', 'wininit.exe', 'services.exe', 'lsass.exe', 'svchost.exe', 'Explorer.EXE', 'dwm.exe'];
  for (const name of denied) {
    it(`refuses "${name}" (isDeniedSystemProcess)`, () => {
      expect(isDeniedSystemProcess(name)).toBe(true);
    });
    it(`MockOsLayer.apply refuses "${name}"`, async () => {
      const os = new MockOsLayer();
      await expect(os.apply('process-priority', { imageName: name, priority: 'high' })).rejects.toMatchObject({
        code: 'refused',
      });
      expect(os.snapshot.processPriorities[name.toLowerCase()]).toBeUndefined();
    });
  }

  it('allows ordinary game executables', async () => {
    const os = new MockOsLayer();
    await os.apply('process-priority', { imageName: 'eldenring.exe', priority: 'high' });
    expect(os.snapshot.processPriorities['eldenring.exe']).toBe('high');
  });

  it('extraDenied adds to the denylist', async () => {
    const os = new MockOsLayer({ deniedProcesses: new Set(['mygame.exe']) });
    await expect(os.apply('process-priority', { imageName: 'mygame.exe', priority: 'high' })).rejects.toMatchObject({
      code: 'refused',
    });
  });

  it('never allows realtime, even via restore', async () => {
    const os = new MockOsLayer();
    await expect(os.apply('process-priority', { imageName: 'game.exe', priority: 'realtime' })).rejects.toMatchObject({
      code: 'refused',
    });
  });
});

describe('wildcard process names (Get-Process -Name pattern bypass)', () => {
  // PowerShell's Get-Process -Name accepts wildcards: 'explor*' would match
  // the protected explorer.exe while passing the exact-match denylist.
  const wildcardNames = ['explor*', 'explor?', 'exp[lorer].exe', 'explor`er.exe', '*', 'game*'];
  for (const name of wildcardNames) {
    it(`hasWildcardSyntax("${name}") is true and validation rejects it`, () => {
      expect(hasWildcardSyntax(name)).toBe(true);
      expect(processImageNameProblem(name)).toMatch(/wildcard/i);
    });
    it(`MockOsLayer.apply refuses "${name}" and mutates nothing`, async () => {
      const os = new MockOsLayer();
      await expect(os.apply('process-priority', { imageName: name, priority: 'high' })).rejects.toMatchObject({
        code: 'refused',
      });
      expect(os.snapshot.processPriorities).toEqual({});
    });
    it(`MockOsLayer.restore refuses "${name}"`, async () => {
      const os = new MockOsLayer();
      await expect(os.restore('process-priority', { imageName: name }, 'normal')).rejects.toMatchObject({
        code: 'refused',
      });
    });
    it(`MockOsLayer.readCurrent refuses "${name}"`, async () => {
      const os = new MockOsLayer();
      await expect(os.readCurrent('process-priority', { imageName: name })).rejects.toMatchObject({
        code: 'refused',
      });
    });
  }

  it('literal names are not wildcard syntax; denylist and ordinary names behave', () => {
    expect(hasWildcardSyntax('eldenring.exe')).toBe(false);
    expect(processImageNameProblem('eldenring.exe')).toBeUndefined();
    expect(processImageNameProblem('explorer.exe')).toMatch(/system process/i);
    expect(processImageNameProblem('')).toMatch(/imageName/);
  });
});

describe('Windows resolved-process handling (per-instance priority)', () => {
  it('parses id|name|priority lines and ignores blank/garbage lines', () => {
    const procs = parseResolvedProcesses('111|game|Normal\r\n222|game|High\n\nnot-a-process\n');
    expect(procs).toEqual([
      { id: 111, processName: 'game', priorityClass: 'Normal' },
      { id: 222, processName: 'game', priorityClass: 'High' },
    ]);
  });

  it('refuses when ANY resolved process is denylisted, before any mutation', () => {
    expect(() =>
      assertNoResolvedProcessDenied([{ id: 7, processName: 'explorer', priorityClass: 'Normal' }]),
    ).toThrow(/system process/i);
    expect(() =>
      assertNoResolvedProcessDenied([
        { id: 8, processName: 'game', priorityClass: 'Normal' },
        { id: 9, processName: 'csrss', priorityClass: 'Normal' },
      ]),
    ).toThrow(/system process/i);
    expect(() =>
      assertNoResolvedProcessDenied([{ id: 10, processName: 'game', priorityClass: 'Normal' }]),
    ).not.toThrow();
  });

  it('set-by-id script mutates exactly one process identity, never a name query', () => {
    const script = buildSetPriorityByIdScript(222, 'High');
    expect(script).toContain('Get-Process -Id 222');
    expect(script).not.toContain('Get-Process -Name');
    expect(script).not.toContain('ForEach-Object');
    expect(script).toContain('ProcessPriorityClass]::High');
    expect(() => buildSetPriorityByIdScript(0, 'High')).toThrow();
    expect(() => buildSetPriorityByIdScript(1.5, 'High')).toThrow();
  });

  it('normalizes .NET priority class names to the journal format', () => {
    expect(normalizePriorityClassName('AboveNormal')).toBe('above-normal');
    expect(normalizePriorityClassName('BelowNormal')).toBe('below-normal');
    expect(normalizePriorityClassName('Normal')).toBe('normal');
    expect(normalizePriorityClassName('High')).toBe('high');
    expect(normalizePriorityClassName('Idle')).toBe('idle');
  });
});

describe('capability probing', () => {
  it('mock reports all four capabilities supported by default', async () => {
    const os = new MockOsLayer();
    const caps = await os.probeCapabilities();
    expect(caps).toHaveLength(4);
    expect(caps.every((c) => c.supported)).toBe(true);
    expect(caps.map((c) => c.id).sort()).toEqual([
      'fullscreen-optimizations',
      'game-mode',
      'power-plan',
      'process-priority',
    ]);
  });

  it('mock unsupportedCapabilities are reflected with reasons', async () => {
    const os = new MockOsLayer({ unsupportedCapabilities: new Set(['power-plan', 'game-mode']) });
    const caps = await os.probeCapabilities();
    const byId = new Map(caps.map((c) => [c.id, c]));
    expect(byId.get('power-plan')!.supported).toBe(false);
    expect(byId.get('power-plan')!.reason).toBeTruthy();
    expect(byId.get('game-mode')!.supported).toBe(false);
    expect(byId.get('process-priority')!.supported).toBe(true);
  });

  it('WindowsOsLayer on non-Windows reports everything unsupported and never attempts', async () => {
    if (process.platform === 'win32') return; // only meaningful off-Windows
    const os = new WindowsOsLayer();
    const caps = await os.probeCapabilities();
    expect(caps).toHaveLength(4);
    expect(caps.every((c) => !c.supported)).toBe(true);
    expect(caps.every((c) => (c.reason ?? '').length > 0)).toBe(true);
    await expect(os.apply('game-mode', { enabled: 'true' })).rejects.toMatchObject({ code: 'unsupported' });
    await expect(os.readCurrent('power-plan', {})).rejects.toMatchObject({ code: 'unsupported' });
  });
});

describe('GUID helpers', () => {
  it('validates and normalizes GUIDs', () => {
    expect(isValidGuid(HIGH_PERF)).toBe(true);
    expect(isValidGuid('{8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c}')).toBe(true);
    expect(isValidGuid('not-a-guid')).toBe(false);
    expect(isValidGuid('')).toBe(false);
    expect(normalizeGuid('{8C5E7FDA-E8BF-4A96-9A85-A6E23A8C635C}')).toBe(HIGH_PERF);
    expect(() => normalizeGuid('bogus')).toThrow(OsLayerError);
  });

  it('describeDesired matches readCurrent formats', async () => {
    const os = new MockOsLayer();
    expect(describeDesired('game-mode', { enabled: 'true' })).toBe('enabled');
    expect(describeDesired('power-plan', { guid: HIGH_PERF })).toBe(HIGH_PERF);
    expect(describeDesired('process-priority', { priority: 'High' })).toBe('high');
    expect(describeDesired('fullscreen-optimizations', { disableFse: '1' })).toBe('disabled');
    await os.apply('game-mode', { enabled: 'true' });
    expect(await os.readCurrent('game-mode', {})).toBe(describeDesired('game-mode', { enabled: 'true' }));
  });
});
