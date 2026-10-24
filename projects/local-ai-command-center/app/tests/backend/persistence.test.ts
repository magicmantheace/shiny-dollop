import { describe, expect, it } from 'vitest';
import { TaskEngine } from '../../electron/main/engine.js';
import { openDatabase } from '../../electron/main/store.js';
import { makeFixture } from './helpers.js';

describe('persistence', () => {
  it('reopen preserves config, task, output, audit; audit append-only', async () => {
    const { engine, db, config, dbPath } = makeFixture();
    engine.saveConfig(config);
    const task = engine.submit({ prompt: 'persist me' });
    await engine.whenIdle();
    expect(engine.getTask(task.id).status).toBe('completed');
    db.close();
    const db2 = openDatabase(dbPath);
    const engine2 = new TaskEngine(db2);
    expect(engine2.getConfig()).toEqual(config);
    const t2 = engine2.getTask(task.id);
    expect(t2.status).toBe('completed');
    expect(t2.output).toContain('persist me');
    expect(engine2.listAudit(500).length).toBeGreaterThan(0);
    expect(() => db2.prepare("UPDATE audit SET event='x'").run()).toThrow();
    expect(() => db2.prepare('DELETE FROM audit').run()).toThrow();
    db2.close();
  });
});
