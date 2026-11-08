import fs from 'node:fs';
import { describe, expect, it } from 'vitest';
import {
  CompanionConfigStore,
  DEFAULT_COMPANION_CONFIG,
  generateCompanionToken,
  type CompanionConfig,
  type CompanionFs,
} from '../src/main/server/companion-config.js';
import { tmpDir } from './helpers.js';

const T0 = 1_700_000_000_000;

describe('CompanionConfigStore', () => {
  it('missing file → defaults, nothing written yet', () => {
    const dir = tmpDir();
    const store = new CompanionConfigStore(dir);
    const result = store.load(T0);
    expect(result.outcome).toBe('fresh-missing');
    expect(result.config).toEqual(DEFAULT_COMPANION_CONFIG);
    // Disabled by default — the server must never start uninvited.
    expect(result.config.enabled).toBe(false);
    expect(fs.existsSync(store.filePath)).toBe(false);
  });

  it('save → load round-trips, written atomically as JSON', () => {
    const dir = tmpDir();
    const store = new CompanionConfigStore(dir);
    const config: CompanionConfig = {
      enabled: true,
      host: '127.0.0.1',
      port: 9999,
      token: 'test-token-not-a-real-one',
    };
    store.save(config);
    expect(fs.existsSync(`${store.filePath}.tmp`)).toBe(false);
    const result = store.load(T0);
    expect(result.outcome).toBe('loaded');
    expect(result.config).toEqual(config);
  });

  it('corrupt JSON → defaults, file renamed aside (never destroyed)', () => {
    const dir = tmpDir();
    const store = new CompanionConfigStore(dir);
    fs.writeFileSync(store.filePath, '{not json', 'utf8');
    const result = store.load(T0);
    expect(result.outcome).toBe('fresh-corrupt');
    expect(result.config).toEqual(DEFAULT_COMPANION_CONFIG);
    expect(result.backupPath).toBeTruthy();
    expect(fs.existsSync(result.backupPath as string)).toBe(true);
    expect(fs.readFileSync(result.backupPath as string, 'utf8')).toBe('{not json');
    expect(fs.existsSync(store.filePath)).toBe(false);
  });

  it('valid JSON with an invalid shape → treated as corrupt', () => {
    const dir = tmpDir();
    const store = new CompanionConfigStore(dir);
    fs.writeFileSync(
      store.filePath,
      JSON.stringify({ enabled: 'yes', host: '0.0.0.0', port: 70000, token: '' }),
      'utf8',
    );
    const result = store.load(T0);
    expect(result.outcome).toBe('fresh-corrupt');
    expect(result.config).toEqual(DEFAULT_COMPANION_CONFIG);
  });

  it('runs against an injected in-memory fs', () => {
    const files = new Map<string, string>();
    const fake: CompanionFs = {
      readFileSync: (p) => {
        const v = files.get(p);
        if (v === undefined) throw new Error('ENOENT');
        return v;
      },
      writeFileSync: (p, data) => {
        files.set(p, data);
      },
      renameSync: (from, to) => {
        const v = files.get(from);
        if (v === undefined) throw new Error('ENOENT');
        files.set(to, v);
        files.delete(from);
      },
      mkdirSync: () => undefined,
    };
    const store = new CompanionConfigStore('/virtual', { fs: fake });
    expect(store.load(T0).outcome).toBe('fresh-missing');
    const config: CompanionConfig = { enabled: false, host: '0.0.0.0', port: 8931, token: 'x' };
    store.save(config);
    expect(store.load(T0).config).toEqual(config);
  });
});

describe('generateCompanionToken', () => {
  it('produces long url-safe tokens, different every time', () => {
    const a = generateCompanionToken();
    const b = generateCompanionToken();
    expect(a).toMatch(/^[A-Za-z0-9_-]{40,}$/);
    expect(b).toMatch(/^[A-Za-z0-9_-]{40,}$/);
    expect(a).not.toBe(b);
  });
});
