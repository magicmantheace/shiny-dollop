import { describe, expect, it } from 'vitest';
import {
  gamesLaunchSchema,
  libraryAddManualSchema,
  libraryRemoveSchema,
  librarySetFavoriteSchema,
  libraryUpdateSchema,
  settingsUpdateSchema,
  sourcesScanSchema,
} from '../../shared/ipc-schemas';

describe('IPC schemas', () => {
  it('accepts a valid addManual payload', () => {
    expect(
      libraryAddManualSchema.parse({ path: '/games/doom.exe', args: ['--a'] }),
    ).toBeTruthy();
  });
  it('rejects missing/empty/wrong-typed fields', () => {
    expect(() => libraryAddManualSchema.parse({})).toThrow();
    expect(() => libraryAddManualSchema.parse({ path: '' })).toThrow();
    expect(() => libraryAddManualSchema.parse({ path: 42 })).toThrow();
    expect(() => libraryAddManualSchema.parse({ path: '/x', args: '--not-an-array' })).toThrow();
  });
  it('rejects unknown extra fields (strict mode)', () => {
    expect(() => libraryAddManualSchema.parse({ path: '/x', execPath: '/evil' })).toThrow();
    expect(() => gamesLaunchSchema.parse({ id: 'a', path: '/evil' })).toThrow();
    expect(() => settingsUpdateSchema.parse({ trackingEnabled: true, admin: true })).toThrow();
  });
  it('accepts valid launch/remove/favorite/update payloads', () => {
    expect(gamesLaunchSchema.parse({ id: 'abc' })).toBeTruthy();
    expect(libraryRemoveSchema.parse({ id: 'abc' })).toBeTruthy();
    expect(librarySetFavoriteSchema.parse({ id: 'abc', favorite: true })).toBeTruthy();
    expect(libraryUpdateSchema.parse({ id: 'abc', title: 'New' })).toBeTruthy();
  });
  it('rejects malformed update/favorite payloads', () => {
    expect(() => libraryUpdateSchema.parse({ id: 'abc', title: '' })).toThrow();
    expect(() => librarySetFavoriteSchema.parse({ id: 'abc' })).toThrow();
    expect(() => sourcesScanSchema.parse({ source: 'gog' })).toThrow();
  });
});
