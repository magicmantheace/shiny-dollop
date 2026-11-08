import { describe, expect, it } from 'vitest';
import { mkdirSync, mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { MockAdapter } from '../../electron/main/adapter.js';
import { TaskEngine } from '../../electron/main/engine.js';
import { insertTask, openDatabase, saveConfig, updateTask } from '../../electron/main/store.js';

describe('startup reconciliation of persisted tasks', () => {
  it('restores queued tasks and marks interrupted running tasks failed with a log entry', async () => {
    const dir = mkdtempSync(join(tmpdir(), 'lacc-recovery-'));
    const ws = join(dir, 'ws');
    mkdirSync(ws, { recursive: true });
    const dbPath = join(dir, 'test.sqlite');
    const config = { mode: 'mock' as const, baseUrl: 'http://127.0.0.1:11434', model: 'mock-echo-1', timeoutMs: 5000, workspaceRoot: ws };

    // Simulate a previous process that died with one running + one queued task.
    const db1 = openDatabase(dbPath);
    saveConfig(db1, config);
    const running = insertTask(db1, { prompt: 'was running', model: config.model, workspaceRoot: ws });
    updateTask(db1, running.id, { status: 'running', startedAt: new Date().toISOString() });
    const queued = insertTask(db1, { prompt: 'was queued', model: config.model, workspaceRoot: ws });
    db1.close();

    // Restart: a new engine over the same database.
    const db2 = openDatabase(dbPath);
    const engine = new TaskEngine(db2, { adapterFactory: () => new MockAdapter({ delayMs: 1 }) });

    const interrupted = engine.getTask(running.id);
    expect(interrupted.status).toBe('failed');
    expect(interrupted.error).toContain('interrupted');
    expect(interrupted.finishedAt).not.toBeNull();
    expect(engine.listTaskLogs(running.id).some((l) => l.message.includes('interrupted'))).toBe(true);

    await engine.whenIdle();
    const restored = engine.getTask(queued.id);
    expect(restored.status).toBe('completed');
    expect(restored.output).toContain('was queued');
    db2.close();
  });
});
