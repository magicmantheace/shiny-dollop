import { describe, expect, it } from 'vitest';
import { TaskEngine } from '../../electron/main/engine.js';
import { MockAdapter } from '../../electron/main/adapter.js';
import { makeFixture, waitForStatus } from './helpers.js';

describe('TaskEngine', () => {
  it('submit -> completed with output and logs', async () => {
    const { engine, db, config } = makeFixture();
    engine.saveConfig(config);
    const task = engine.submit({ prompt: 'Say hello' });
    await engine.whenIdle();
    const done = engine.getTask(task.id);
    expect(done.status).toBe('completed');
    expect(done.output).toContain('Say hello');
    const logs = engine.listTaskLogs(task.id);
    expect(logs.length).toBeGreaterThan(0);
    expect(logs.some((l) => l.level === 'adapter')).toBe(true);
    db.close();
  });
  it('unavailable endpoint -> task failed ENDPOINT_UNREACHABLE', async () => {
    const { engine, db, config } = makeFixture({ mode: 'live', baseUrl: 'http://127.0.0.1:1', timeoutMs: 2000 });
    engine.saveConfig(config);
    const task = engine.submit({ prompt: 'hi' });
    await engine.whenIdle();
    const done = engine.getTask(task.id);
    expect(done.status).toBe('failed');
    expect(done.error).toContain('ENDPOINT_UNREACHABLE');
    db.close();
  });
  it('timeout via hanging adapter -> ENDPOINT_TIMEOUT', async () => {
    const { db, ws } = makeFixture();
    const hanging = {
      health: async () => ({ models: ['x'] }),
      generate: async () => new Promise<{ text: string }>(() => { /* never */ }),
    };
    const engine = new TaskEngine(db, { adapterFactory: () => hanging as unknown as MockAdapter });
    engine.saveConfig({ mode: 'mock', baseUrl: 'http://127.0.0.1:11434', model: 'mock-echo-1', timeoutMs: 100, workspaceRoot: ws });
    const task = engine.submit({ prompt: 'hang please' });
    await engine.whenIdle();
    const done = engine.getTask(task.id);
    expect(done.status).toBe('failed');
    expect(done.error).toContain('ENDPOINT_TIMEOUT');
    db.close();
  });
  it('cancellation of running [mock:hang] -> cancelled + audit', async () => {
    const { engine, db, config } = makeFixture();
    engine.saveConfig(config);
    const task = engine.submit({ prompt: '[mock:hang] wait' });
    await waitForStatus(engine, task.id, 'running');
    const cancelled = await engine.cancel(task.id);
    expect(cancelled.status).toBe('cancelled');
    expect(engine.getTask(task.id).status).toBe('cancelled');
    const audit = engine.listAudit(500);
    expect(audit.some((a) => a.event === 'task.cancelled')).toBe(true);
    db.close();
  });
  it('queued cancel', async () => {
    const { engine, db, config } = makeFixture();
    engine.saveConfig(config);
    const first = engine.submit({ prompt: '[mock:hang] first' });
    await waitForStatus(engine, first.id, 'running');
    const second = engine.submit({ prompt: 'second queued' });
    expect(engine.getTask(second.id).status).toBe('queued');
    const cancelled = await engine.cancel(second.id);
    expect(cancelled.status).toBe('cancelled');
    await engine.cancel(first.id);
    await engine.whenIdle();
    db.close();
  });
});
