import { describe, expect, it, afterEach } from 'vitest';
import {
  activateProfile,
  bridge,
  deleteProfile,
  listCapabilities,
  previewProfile,
  restoreAll,
  takeSnapshot,
} from '../src/gpp';
import {
  callArgs,
  clearGppMock,
  installGppMock,
  mockCapabilities,
  mockProfile,
} from './mocks';

afterEach(() => {
  clearGppMock();
});

describe('gpp bridge wrapper', () => {
  it('throws an actionable error when window.gpp is missing', () => {
    clearGppMock();
    expect(() => bridge()).toThrow(/window\.gpp.*not available/);
  });

  it('lists capabilities from the bridge', async () => {
    const mock = installGppMock({
      async getCapabilities() {
        return {
          capabilities: mockCapabilities({ 'power-plan': { supported: false, reason: 'no admin' } }),
        };
      },
    });
    const caps = await listCapabilities();
    expect(caps).toHaveLength(4);
    expect(caps.find((c) => c.id === 'power-plan')?.supported).toBe(false);
    expect(mock.calls['getCapabilities']).toHaveLength(1);
  });

  it('passes profileId through to preview', async () => {
    const mock = installGppMock();
    await previewProfile('profile-9');
    expect(callArgs(mock, 'previewProfile')[0]).toEqual({ profileId: 'profile-9' });
  });

  it('activate always sends approved: true', async () => {
    const mock = installGppMock();
    await activateProfile('profile-1', true);
    expect(callArgs(mock, 'activateProfile')[0]).toEqual({
      profileId: 'profile-1',
      approved: true,
    });
  });

  it('delete passes the id through', async () => {
    const mock = installGppMock();
    await deleteProfile('profile-7');
    expect(callArgs(mock, 'deleteProfile')[0]).toEqual({ id: 'profile-7' });
  });

  it('restoreAll returns the result payload', async () => {
    installGppMock();
    const result = await restoreAll();
    expect(result.ok).toBe(true);
    expect(result.rolledBack).toEqual(['journal-1', 'journal-2']);
  });

  it('takeSnapshot forwards the label', async () => {
    const mock = installGppMock();
    const snap = await takeSnapshot('before elden ring');
    expect(snap.label).toBe('before elden ring');
    expect(callArgs(mock, 'takeSnapshot')[0]).toEqual({ label: 'before elden ring' });
  });

  it('converts an { error } response into a thrown Error', async () => {
    installGppMock({
      async createProfile() {
        return { error: 'name taken' };
      },
    });
    const { createProfile } = await import('../src/gpp');
    await expect(createProfile({ name: 'x', changes: [] })).rejects.toThrow(
      /name taken/,
    );
  });

  it('mock profile helper builds a sane default', () => {
    const p = mockProfile();
    expect(p.changes).toHaveLength(2);
    expect(p.name).toBe('Test Profile');
  });
});
