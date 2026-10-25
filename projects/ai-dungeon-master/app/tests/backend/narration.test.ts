import { describe, expect, it } from 'vitest';
import { isLoopbackUrl } from '../../electron/main/narrator.js';
import { makeFixture } from './helpers.js';

async function setup(fx: ReturnType<typeof makeFixture>) {
  const campaign = await fx.service.campaignsCreate({ name: 'Narration', seed: 'narr-seed' });
  const roll = await fx.service.diceRoll(campaign.id, { notation: '2d6', label: 'omen' });
  return { campaign, roll };
}

describe('narration is flavor only', () => {
  it('attaches mock narration without moving any rules state', async () => {
    const fx = makeFixture();
    const { campaign, roll } = await setup(fx);
    const hero = await fx.service.charactersCreate(campaign.id, {
      kind: 'pc',
      name: 'Wren',
      hpMax: 10,
    });
    const before = {
      diceState: (await fx.service.campaignsGet(campaign.id)).diceState,
      logLength: (await fx.service.logList(campaign.id)).length,
      characters: await fx.service.charactersList(campaign.id),
    };
    const res = await fx.service.narrate(roll.entry.id);
    expect(res.source).toBe('mock');
    expect(res.entry.narration).toBeTruthy();
    expect(res.entry.narrationSource).toBe('mock');
    // Nothing but the narration fields changed: the entry's rules data is
    // identical, the dice stream did not advance, no new log entries were
    // appended, and character state is untouched.
    expect(res.entry.text).toBe(roll.entry.text);
    expect(res.entry.detail).toEqual(roll.entry.detail);
    expect(res.entry.seq).toBe(roll.entry.seq);
    const after = {
      diceState: (await fx.service.campaignsGet(campaign.id)).diceState,
      logLength: (await fx.service.logList(campaign.id)).length,
      characters: await fx.service.charactersList(campaign.id),
    };
    expect(after.diceState).toBe(before.diceState);
    expect(after.logLength).toBe(before.logLength);
    expect(after.characters).toEqual(before.characters);
    expect(after.characters.find((c) => c.id === hero.id)?.hpCurrent).toBe(10);
  });

  it('falls back to mock narration when the local endpoint is unreachable', async () => {
    const fx = makeFixture();
    const { roll } = await setup(fx);
    await fx.service.settingsUpdate({
      narrator: 'local',
      endpoint: 'http://127.0.0.1:9', // discard port: nothing listens there
      model: 'no-such-model',
    });
    const res = await fx.service.narrate(roll.entry.id);
    expect(res.source).toBe('mock-fallback');
    expect(res.entry.narration).toBeTruthy();
  });

  it('rejects cloud endpoints in settings (loopback only)', async () => {
    const fx = makeFixture();
    await expect(
      fx.service.settingsUpdate({
        narrator: 'local',
        endpoint: 'https://api.example.com',
        model: 'gpt',
      }),
    ).rejects.toMatchObject({ code: 'INPUT_INVALID' });
    expect(isLoopbackUrl('http://127.0.0.1:11434')).toBe(true);
    expect(isLoopbackUrl('http://localhost:11434')).toBe(true);
    expect(isLoopbackUrl('https://example.com')).toBe(false);
  });

  it('rejects .local names: mDNS hosts are other LAN machines, not loopback', async () => {
    expect(isLoopbackUrl('http://my-mac.local:11434')).toBe(false);
    expect(isLoopbackUrl('http://ollama.local')).toBe(false);
    expect(isLoopbackUrl('http://localhost.local:11434')).toBe(false);
    const fx = makeFixture();
    await expect(
      fx.service.settingsUpdate({
        narrator: 'local',
        endpoint: 'http://my-mac.local:11434',
        model: 'llama',
      }),
    ).rejects.toMatchObject({ code: 'INPUT_INVALID' });
  });

  it('never follows a redirect from the loopback endpoint (prompt is not forwarded)', async () => {
    const { createServer } = await import('node:http');
    let targetHits = 0;
    const target = createServer((_req, res) => {
      targetHits += 1;
      res.writeHead(200, { 'content-type': 'application/json' });
      res.end(JSON.stringify({ response: 'Leaked narration.' }));
    });
    await new Promise<void>((resolve) => target.listen(0, '127.0.0.1', resolve));
    const targetAddress = target.address();
    if (!targetAddress || typeof targetAddress === 'string') throw new Error('no address');
    const redirector = createServer((_req, res) => {
      // 307 preserves method + body on a following client — exactly the
      // leak path. Even a loopback target must receive NOTHING, because
      // the same mechanism reaches non-loopback destinations.
      res.writeHead(307, { location: `http://127.0.0.1:${targetAddress.port}/api/generate` });
      res.end();
    });
    await new Promise<void>((resolve) => redirector.listen(0, '127.0.0.1', resolve));
    try {
      const address = redirector.address();
      if (!address || typeof address === 'string') throw new Error('no address');
      const fx = makeFixture();
      const { roll } = await setup(fx);
      await fx.service.settingsUpdate({
        narrator: 'local',
        endpoint: `http://127.0.0.1:${address.port}`,
        model: 'test-model',
      });
      const res = await fx.service.narrate(roll.entry.id);
      // Narration fell back to the mock; the redirect target never saw
      // the prompt-bearing POST.
      expect(res.source).toBe('mock-fallback');
      expect(targetHits).toBe(0);
    } finally {
      redirector.close();
      target.close();
    }
  });

  it('uses a local endpoint when one answers (loopback test server)', async () => {
    const { createServer } = await import('node:http');
    const server = createServer((req, res) => {
      let body = '';
      req.on('data', (chunk) => (body += chunk));
      req.on('end', () => {
        expect(req.url).toBe('/api/generate');
        res.writeHead(200, { 'content-type': 'application/json' });
        res.end(JSON.stringify({ response: 'Rain hisses on hot stone.' }));
      });
    });
    await new Promise<void>((resolve) => server.listen(0, '127.0.0.1', resolve));
    try {
      const address = server.address();
      if (!address || typeof address === 'string') throw new Error('no address');
      const fx = makeFixture();
      const { roll } = await setup(fx);
      await fx.service.settingsUpdate({
        narrator: 'local',
        endpoint: `http://127.0.0.1:${address.port}`,
        model: 'test-model',
      });
      const res = await fx.service.narrate(roll.entry.id);
      expect(res.source).toBe('local');
      expect(res.entry.narration).toBe('Rain hisses on hot stone.');
    } finally {
      server.close();
    }
  });
});
