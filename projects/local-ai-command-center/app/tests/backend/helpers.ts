import { mkdtempSync, mkdirSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { TaskEngine } from '../../electron/main/engine.js';
import { openDatabase } from '../../electron/main/store.js';
import type { EndpointConfig } from '../../shared/types.js';

export function makeFixture(configOverrides?: Partial<EndpointConfig>) {
  const dir = mkdtempSync(join(tmpdir(), 'lacc-test-'));
  const ws = join(dir, 'ws');
  mkdirSync(ws, { recursive: true });
  const dbPath = join(dir, 'test.sqlite');
  const db = openDatabase(dbPath);
  const engine = new TaskEngine(db);
  const config: EndpointConfig = {
    mode: 'mock',
    baseUrl: 'http://127.0.0.1:11434',
    model: 'mock-echo-1',
    timeoutMs: 5000,
    workspaceRoot: ws,
    ...configOverrides,
  };
  return { dir, ws, dbPath, db, engine, config };
}
export async function waitForStatus(engine: TaskEngine, id: string, status: string, timeoutMs = 5000): Promise<void> {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    if (engine.getTask(id).status === status) return;
    await new Promise((r) => setTimeout(r, 10));
  }
  throw new Error(`timed out waiting for ${status}, got ${engine.getTask(id).status}`);
}
