import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';
import { createSave, parse, serialize, type SaveEnvelope } from 'drabbit-core';
import { SAVE_FILENAME, SaveStore } from '../src/main/save-store.js';
import { tmpDir } from './helpers.js';

const T0 = 1_700_000_000_000;

function freshEnvelope(now: number): SaveEnvelope {
  return createSave({ id: 'test-pet', name: 'Pip', fur: 'royal' }, now);
}

describe('SaveStore', () => {
  it('round-trips a saved envelope byte-identically', () => {
    const dir = tmpDir();
    const store = new SaveStore(dir);
    const env = freshEnvelope(T0);
    store.save(env);

    const result = new SaveStore(dir).loadOrCreate(T0 + 1000, freshEnvelope);
    expect(result.outcome).toBe('loaded');
    expect(serialize(result.envelope)).toBe(serialize(env));
  });

  it('starts fresh when the save file is missing', () => {
    const dir = tmpDir();
    const store = new SaveStore(dir);
    const result = store.loadOrCreate(T0, freshEnvelope);
    expect(result.outcome).toBe('fresh-missing');
    expect(result.envelope.pet.id).toBe('test-pet');
    expect(result.backupPath).toBeUndefined();
    // No corrupt-backup litter on a clean first run.
    expect(fs.readdirSync(dir)).toEqual([]);
  });

  it('recovers from a corrupt save: renamed aside, never destroyed, fresh egg returned', () => {
    const dir = tmpDir();
    const store = new SaveStore(dir);
    const garbage = 'this is not a save {{{';
    fs.writeFileSync(path.join(dir, SAVE_FILENAME), garbage, 'utf8');

    const logs: string[] = [];
    const loggingStore = new SaveStore(dir, (m) => logs.push(m));
    const result = loggingStore.loadOrCreate(T0 + 5000, freshEnvelope);

    expect(result.outcome).toBe('fresh-corrupt');
    expect(result.envelope.pet.id).toBe('test-pet');
    expect(result.backupPath).toBeDefined();
    // The corrupt bytes survive intact at the backup path…
    expect(fs.readFileSync(result.backupPath as string, 'utf8')).toBe(garbage);
    // …and the original path is clear for the fresh save.
    expect(fs.existsSync(path.join(dir, SAVE_FILENAME))).toBe(false);
    expect(logs.join('\n')).toMatch(/corrupt/i);
  });

  it('treats valid JSON with an invalid shape as corrupt', () => {
    const dir = tmpDir();
    fs.writeFileSync(path.join(dir, SAVE_FILENAME), '{"hello":"world"}', 'utf8');
    const result = new SaveStore(dir).loadOrCreate(T0, freshEnvelope);
    expect(result.outcome).toBe('fresh-corrupt');
  });

  it('writes atomically: no .tmp file remains after save', () => {
    const dir = tmpDir();
    const store = new SaveStore(dir);
    store.save(freshEnvelope(T0));
    expect(fs.readdirSync(dir)).toEqual([SAVE_FILENAME]);
    // And what landed on disk parses cleanly.
    expect(parse(fs.readFileSync(store.filePath, 'utf8')).pet.id).toBe('test-pet');
  });
});
