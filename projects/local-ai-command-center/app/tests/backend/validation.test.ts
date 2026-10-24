import { describe, expect, it } from 'vitest';
import { MAX_PROMPT_CHARS } from '../../shared/types.js';
import { makeFixture } from './helpers.js';

describe('validation', () => {
  it('empty prompt -> TASK_INVALID', () => {
    const { engine, db, config } = makeFixture();
    engine.saveConfig(config);
    expect(() => engine.submit({ prompt: '   ' })).toThrowError(expect.objectContaining({ code: 'TASK_INVALID' }));
    expect(() => engine.submit({ prompt: '' })).toThrowError(expect.objectContaining({ code: 'TASK_INVALID' }));
    db.close();
  });
  it('oversize prompt -> INPUT_TOO_LARGE', () => {
    const { engine, db, config } = makeFixture();
    engine.saveConfig(config);
    expect(() => engine.submit({ prompt: 'x'.repeat(MAX_PROMPT_CHARS + 1) })).toThrowError(expect.objectContaining({ code: 'INPUT_TOO_LARGE' }));
    db.close();
  });
  it('health with no config -> ENDPOINT_NOT_CONFIGURED', async () => {
    const { engine, db } = makeFixture();
    await expect(engine.health()).rejects.toMatchObject({ code: 'ENDPOINT_NOT_CONFIGURED' });
    db.close();
  });
  it('health with dead endpoint returns ok:false not throw', async () => {
    const { engine, db, config } = makeFixture({ mode: 'live', baseUrl: 'http://127.0.0.1:1', timeoutMs: 2000 });
    engine.saveConfig(config);
    const h = await engine.health();
    expect(h.ok).toBe(false);
    expect(h.message).toBeTruthy();
    db.close();
  });
  it('cancel unknown -> TASK_NOT_FOUND', async () => {
    const { engine, db, config } = makeFixture();
    engine.saveConfig(config);
    await expect(engine.cancel('no-such-id')).rejects.toMatchObject({ code: 'TASK_NOT_FOUND' });
    db.close();
  });
});
