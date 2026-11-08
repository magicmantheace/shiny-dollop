import { describe, expect, it } from 'vitest';
import {
  backupCreateSchema,
  backupRestoreSchema,
  emptySchema,
  gameAddSchema,
  scheduleSetSchema,
} from '../../shared/schemas';

describe('IPC zod schemas', () => {
  it('gameAddSchema trims and requires a non-empty name and save path', () => {
    const parsed = gameAddSchema.parse({ name: '  Skyrim  ', savePath: 'C:\\saves', source: 'steam' });
    expect(parsed.name).toBe('Skyrim');
    expect(parsed.source).toBe('steam');
    expect(() => gameAddSchema.parse({ name: '   ', savePath: 'C:\\saves' })).toThrow();
    expect(() => gameAddSchema.parse({ name: 'X', savePath: '' })).toThrow();
  });

  it('gameAddSchema defaults source to manual', () => {
    expect(gameAddSchema.parse({ name: 'X', savePath: 'C:\\saves' }).source).toBe('manual');
  });

  it('backupRestoreSchema requires confirmed to be literally true', () => {
    expect(backupRestoreSchema.parse({ backupId: 1, confirmed: true }).confirmed).toBe(true);
    expect(() => backupRestoreSchema.parse({ backupId: 1, confirmed: false })).toThrow();
    expect(() => backupRestoreSchema.parse({ backupId: 1 })).toThrow();
    expect(() => backupRestoreSchema.parse({ backupId: 1, confirmed: 'yes' })).toThrow();
  });

  it('backupCreateSchema requires a positive game id', () => {
    expect(() => backupCreateSchema.parse({ gameId: 0 })).toThrow();
    expect(() => backupCreateSchema.parse({ gameId: -3 })).toThrow();
    expect(backupCreateSchema.parse({ gameId: 7, label: 'before boss' }).label).toBe('before boss');
  });

  it('scheduleSetSchema bounds intervalMinutes to 5 minutes .. 30 days', () => {
    expect(scheduleSetSchema.parse({ gameId: 1, intervalMinutes: 60 }).enabled).toBe(true);
    expect(() => scheduleSetSchema.parse({ gameId: 1, intervalMinutes: 4 })).toThrow();
    expect(() => scheduleSetSchema.parse({ gameId: 1, intervalMinutes: 43201 })).toThrow();
    expect(() => scheduleSetSchema.parse({ gameId: 1, intervalMinutes: 1.5 })).toThrow();
  });

  it('emptySchema accepts an empty object', () => {
    expect(emptySchema.parse({})).toEqual({});
  });
});
