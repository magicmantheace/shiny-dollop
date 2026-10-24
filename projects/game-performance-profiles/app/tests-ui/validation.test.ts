import { describe, expect, it } from 'vitest';
import {
  ABS_EXE_PATH_RE,
  GUID_RE,
  PROCESS_NAME_RE,
  changeSummary,
  defaultParams,
  validateChangeParams,
  validateProfileName,
} from '../src/validation';

describe('validateProfileName', () => {
  it('rejects an empty name', () => {
    expect(validateProfileName('')).toBe('Profile name is required.');
  });

  it('rejects a whitespace-only name', () => {
    expect(validateProfileName('   ')).toBe('Profile name is required.');
  });

  it('rejects names longer than 80 characters', () => {
    expect(validateProfileName('x'.repeat(81))).toContain('80 characters');
  });

  it('accepts a normal name', () => {
    expect(validateProfileName('Elden Ring — high performance')).toBeNull();
  });
});

describe('GUID validation', () => {
  it('accepts a lowercase GUID', () => {
    expect(GUID_RE.test('381b4222-f694-41f0-9685-ff5bb260df2e')).toBe(true);
  });

  it('accepts an uppercase GUID', () => {
    expect(GUID_RE.test('381B4222-F694-41F0-9685-FF5BB260DF2E')).toBe(true);
  });

  it('rejects a non-GUID string', () => {
    expect(GUID_RE.test('not-a-guid')).toBe(false);
  });

  it('rejects a GUID with a wrong segment length', () => {
    expect(GUID_RE.test('381b4222-f694-41f0-9685-ff5bb260df2')).toBe(false);
  });

  it('power-plan with a bad GUID produces an actionable error', () => {
    const errs = validateChangeParams('power-plan', { guid: 'junk' });
    expect(errs.length).toBeGreaterThan(0);
    expect(errs[0]).toContain('GUID');
  });

  it('power-plan with a missing GUID complains about picking a plan', () => {
    const errs = validateChangeParams('power-plan', { guid: '' });
    expect(errs.join(' ')).toContain('powercfg');
  });

  it('power-plan with a valid GUID is clean', () => {
    expect(
      validateChangeParams('power-plan', {
        guid: '381b4222-f694-41f0-9685-ff5bb260df2e',
      }),
    ).toEqual([]);
  });
});

describe('process-priority validation', () => {
  it('accepts a normal exe name', () => {
    expect(PROCESS_NAME_RE.test('eldenring.exe')).toBe(true);
  });

  it('rejects a name without .exe', () => {
    expect(PROCESS_NAME_RE.test('eldenring')).toBe(false);
  });

  it('rejects an empty process name with a helpful message', () => {
    const errs = validateChangeParams('process-priority', {
      process: '',
      priority: 'high',
    });
    expect(errs.join(' ')).toContain('game.exe');
  });

  it('rejects realtime and other invalid priorities', () => {
    const errs = validateChangeParams('process-priority', {
      process: 'game.exe',
      priority: 'realtime',
    });
    expect(errs.join(' ')).toContain('above-normal or high');
  });

  it('accepts high priority', () => {
    expect(
      validateChangeParams('process-priority', {
        process: 'game.exe',
        priority: 'high',
      }),
    ).toEqual([]);
  });
});

describe('game-mode validation', () => {
  it('accepts on and off', () => {
    expect(validateChangeParams('game-mode', { enabled: 'true' })).toEqual([]);
    expect(validateChangeParams('game-mode', { enabled: 'false' })).toEqual([]);
  });

  it('rejects anything else', () => {
    expect(validateChangeParams('game-mode', { enabled: 'maybe' }).length).toBeGreaterThan(0);
  });
});

describe('fullscreen-optimizations validation', () => {
  it('accepts an absolute exe path', () => {
    expect(ABS_EXE_PATH_RE.test('C:\\Games\\MyGame\\game.exe')).toBe(true);
  });

  it('accepts a UNC path', () => {
    expect(ABS_EXE_PATH_RE.test('\\\\server\\share\\game.exe')).toBe(true);
  });

  it('rejects a bare filename (not absolute)', () => {
    expect(ABS_EXE_PATH_RE.test('game.exe')).toBe(false);
  });

  it('rejects a non-exe path', () => {
    expect(ABS_EXE_PATH_RE.test('C:\\Games\\readme.txt')).toBe(false);
  });

  it('full change validation flags a bad path', () => {
    const errs = validateChangeParams('fullscreen-optimizations', {
      exePath: 'game.exe',
      enabled: 'true',
    });
    expect(errs.join(' ')).toContain('absolute Windows path');
  });

  it('a valid fullscreen-optimizations change is clean', () => {
    expect(
      validateChangeParams('fullscreen-optimizations', {
        exePath: 'C:\\Games\\MyGame\\game.exe',
        enabled: 'false',
      }),
    ).toEqual([]);
  });
});

describe('change helpers', () => {
  it('defaultParams covers every kind', () => {
    expect(defaultParams('game-mode')).toEqual({ enabled: 'true' });
    expect(defaultParams('power-plan')).toEqual({ guid: '' });
    expect(defaultParams('process-priority')).toEqual({
      process: '',
      priority: 'above-normal',
    });
    expect(defaultParams('fullscreen-optimizations')).toEqual({
      exePath: '',
      enabled: 'false',
    });
  });

  it('changeSummary renders a readable line', () => {
    expect(
      changeSummary({ kind: 'game-mode', params: { enabled: 'true' } }),
    ).toContain('on');
    expect(
      changeSummary({
        kind: 'process-priority',
        params: { process: 'game.exe', priority: 'high' },
      }),
    ).toContain('game.exe');
  });
});
