/**
 * Tests for the Battle.net adapter and the open-client action.
 *
 * Design under test (see docs/BATTLENET_INVESTIGATION.md): per-game
 * discovery is unsupported, so the adapter detects the client and the
 * launcher offers an explicit "Open Battle.net" action. Nothing is
 * invented: no product IDs, no deep links, no fabricated game rows.
 */
import { afterEach, describe, expect, it } from 'vitest';
import { BattleNetAdapter } from '../../electron/main/sources/battlenet/adapter';
import { IpcChannels } from '../../shared/ipc-channels';
import type { SourceStatus } from '../../shared/types';
import { createTestContext, type TestContext } from './helpers';
import { FakeBattleNetOs, fakeBattleNetInstall } from '../battlenet-helpers';

function windowsOs(): FakeBattleNetOs {
  const os = new FakeBattleNetOs();
  os.platform = 'win32';
  return fakeBattleNetInstall(os);
}

describe('probe', () => {
  it('finds the client via %ProgramFiles(x86)%', () => {
    const r = new BattleNetAdapter(windowsOs()).probe();
    expect(r.status).toBe('installed');
    expect(r.clientExe).toBe('C:\\Program Files (x86)\\Battle.net\\Battle.net.exe');
    expect(r.detectedVia).toContain('ProgramFiles(x86)');
  });

  it('reports unavailable when the client exe is absent', () => {
    const os = new FakeBattleNetOs();
    os.platform = 'win32';
    os.setEnv('ProgramFiles(x86)', 'C:\\Program Files (x86)');
    const r = new BattleNetAdapter(os).probe();
    expect(r.status).toBe('unavailable');
    expect(r.clientExe).toBeNull();
    expect(r.reason).toContain('not found');
  });

  it('degrades honestly off Windows', () => {
    const os = new FakeBattleNetOs();
    os.platform = 'linux';
    const r = new BattleNetAdapter(os).probe();
    expect(r.status).toBe('unavailable');
    expect(r.reason).toContain('Windows');
  });
});

describe('scan', () => {
  it('completes with zero games and an explanatory warning', () => {
    const r = new BattleNetAdapter(windowsOs()).scan();
    expect(r.status).toBe('completed');
    expect(r.warnings.length).toBeGreaterThan(0);
    expect(r.warnings[0]).toContain('not supported');
  });
});

let ctx: TestContext | null = null;
afterEach(() => {
  ctx?.close();
  ctx = null;
});

describe('sources.status / sources.scan', () => {
  it('reports Battle.net detected and explains manual registration', async () => {
    ctx = createTestContext({ battleNetOs: windowsOs() });
    const res = await ctx.call(IpcChannels.sourcesStatus, {});
    expect(res.ok).toBe(true);
    const bnet = (res.data as SourceStatus[]).find((s) => s.source === 'battlenet')!;
    expect(bnet.available).toBe(true);
    expect(bnet.reason).toContain('Battle.net client found');
  });

  it('scan completes without inventing games', async () => {
    ctx = createTestContext({ battleNetOs: windowsOs() });
    const res = await ctx.call(IpcChannels.sourcesScan, { source: 'battlenet' });
    expect(res.ok).toBe(true);
    expect((res.data as { gamesFound: number }).gamesFound).toBe(0);
    const list = await ctx.call(IpcChannels.libraryList, { source: 'battlenet' });
    expect((list.data as unknown[])).toHaveLength(0);
  });

  it('scan records its honest status in the scan log', async () => {
    ctx = createTestContext({ battleNetOs: windowsOs() });
    await ctx.call(IpcChannels.sourcesScan, { source: 'battlenet' });
    const res = await ctx.call(IpcChannels.sourcesStatus, {});
    const bnet = (res.data as SourceStatus[]).find((s) => s.source === 'battlenet')!;
    expect(bnet.lastScanAt).not.toBeNull();
  });
});

describe('sources.openClient', () => {
  it('spawns the validated Battle.net client exe with shell:false and no args', async () => {
    ctx = createTestContext({ battleNetOs: windowsOs() });
    const res = await ctx.call(IpcChannels.sourcesOpenClient, { source: 'battlenet' });
    expect(res.ok).toBe(true);
    expect((res.data as { opened: boolean }).opened).toBe(true);
    expect(ctx.stub.calls).toHaveLength(1);
    const call = ctx.stub.calls[0]!;
    expect(call.exe).toBe('C:\\Program Files (x86)\\Battle.net\\Battle.net.exe');
    expect(call.args).toEqual([]);
    expect((call.opts as { shell: boolean }).shell).toBe(false);
  });

  it('fails honestly when the client is absent', async () => {
    ctx = createTestContext({ battleNetOs: new FakeBattleNetOs() });
    const res = await ctx.call(IpcChannels.sourcesOpenClient, { source: 'battlenet' });
    expect(res.ok).toBe(false);
    expect(res.error?.code).toBe('CLIENT_NOT_FOUND');
    expect(ctx.stub.calls).toHaveLength(0);
  });

  it('opens the Epic launcher via the documented URI', async () => {
    const opened: string[] = [];
    ctx = createTestContext({
      openExternalImpl: async (uri: string) => {
        opened.push(uri);
      },
    });
    const res = await ctx.call(IpcChannels.sourcesOpenClient, { source: 'epic' });
    expect(res.ok).toBe(true);
    expect(opened).toEqual(['com.epicgames.launcher://']);
  });

  it('rejects an unexpected source value at the schema boundary', async () => {
    ctx = createTestContext({});
    const res = await ctx.call(IpcChannels.sourcesOpenClient, { source: 'steam' });
    expect(res.ok).toBe(false);
    expect(res.error?.code).toBe('VALIDATION_ERROR');
  });
});
