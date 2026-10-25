import { describe, expect, it } from 'vitest';
import { createHandlers } from '../../electron/main/ipc.js';
import { LACC_IPC_CHANNELS } from '../../shared/types.js';
import { makeFixture } from './helpers.js';

// ipcMain.handle can only transport the error *message* back to the renderer
// (Electron docs), so handlers must return a structured success/error
// envelope as data and let the preload unwrap it — throwing { code, message }
// through the boundary loses the code (finding: ipc.ts transport).
describe('IPC envelope transport', () => {
  it('success resolves to { ok: true, value }', async () => {
    const { engine, db } = makeFixture();
    const handlers = createHandlers(engine, async () => null);
    const result = await handlers[LACC_IPC_CHANNELS.configGet]!();
    expect(result).toEqual({ ok: true, value: null });
    db.close();
  });

  it('failure resolves (does not throw) to { ok: false, error: { code, message } } preserving the code', async () => {
    const { engine, db } = makeFixture();
    const handlers = createHandlers(engine, async () => null);
    // Invalid config payload -> CONFIG_INVALID from the zod/engine boundary.
    const result = (await handlers[LACC_IPC_CHANNELS.configSave]!({
      mode: 'live',
      baseUrl: 'http://example.com:9999',
      model: 'm',
      timeoutMs: 1000,
      workspaceRoot: '/tmp/ws',
    })) as { ok: boolean; error?: { code: string; message: string } };
    expect(result.ok).toBe(false);
    expect(result.error?.code).toBe('CONFIG_INVALID');
    expect(typeof result.error?.message).toBe('string');
    db.close();
  });

  it('domain errors keep their named code (PROPOSAL_NOT_FOUND)', async () => {
    const { engine, db } = makeFixture();
    const handlers = createHandlers(engine, async () => null);
    const result = (await handlers[LACC_IPC_CHANNELS.proposalsApprove]!(
      'no-such-proposal',
    )) as { ok: boolean; error?: { code: string; message: string } };
    expect(result.ok).toBe(false);
    expect(result.error?.code).toBe('PROPOSAL_NOT_FOUND');
    db.close();
  });
});
