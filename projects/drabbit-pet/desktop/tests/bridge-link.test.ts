import { describe, expect, it } from 'vitest';
import {
  bridgeReactionFor,
  parseBridgeDisplayState,
  type BridgeDisplayState,
  type BridgeReaction,
} from '../src/shared/bridge-reaction.js';
import {
  BridgeLinkService,
  bridgeStateCandidates,
} from '../src/main/bridge-link.js';
import type { Scheduler } from '../src/main/tick-service.js';

const state = (s: string): BridgeDisplayState => ({
  state: s,
  art: s,
  label: s,
  since: 100,
  updatedAt: 100,
});

const NOW = 1_700_000_000_000;

describe('parseBridgeDisplayState', () => {
  it('parses a well-formed file', () => {
    const parsed = parseBridgeDisplayState(
      JSON.stringify({
        state: 'working', art: 'working', label: 'Working',
        since: 12.5, updated_at: 13,
      }),
    );
    expect(parsed).toEqual({
      state: 'working', art: 'working', label: 'Working',
      since: 12.5, updatedAt: 13,
    });
  });

  it('rejects junk, non-objects, and a missing/empty state', () => {
    expect(parseBridgeDisplayState('not json')).toBeNull();
    expect(parseBridgeDisplayState('[1,2]')).toBeNull();
    expect(parseBridgeDisplayState('{"art":"idle"}')).toBeNull();
    expect(parseBridgeDisplayState('{"state":""}')).toBeNull();
    expect(parseBridgeDisplayState('{"state":42}')).toBeNull();
  });

  it('tolerates missing optional fields', () => {
    const parsed = parseBridgeDisplayState('{"state":"idle"}');
    expect(parsed?.state).toBe('idle');
    expect(parsed?.since).toBe(0);
  });
});

describe('bridgeReactionFor', () => {
  it('reacts to busy states and celebrate', () => {
    expect(bridgeReactionFor('idle', state('working'), 'Pip', NOW)?.kind)
      .toBe('working');
    expect(bridgeReactionFor('idle', state('session'), 'Pip', NOW)?.kind)
      .toBe('session');
    expect(bridgeReactionFor('connecting', state('celebrate'), 'Pip', NOW)?.kind)
      .toBe('celebrate');
  });

  it('surfaces alert even on first observation', () => {
    const r = bridgeReactionFor(null, state('alert'), 'Pip', NOW);
    expect(r?.kind).toBe('alert');
    expect(r?.text).toContain('attention');
  });

  it('stays quiet for repeats, connecting, and first-sighting calm', () => {
    expect(bridgeReactionFor('working', state('working'), 'Pip', NOW)).toBeNull();
    expect(bridgeReactionFor('idle', state('connecting'), 'Pip', NOW)).toBeNull();
    expect(bridgeReactionFor(null, state('idle'), 'Pip', NOW)).toBeNull();
    expect(bridgeReactionFor(null, state('connecting'), 'Pip', NOW)).toBeNull();
  });

  it('relaxes when a busy spell ends, and clears after an alert', () => {
    expect(bridgeReactionFor('working', state('idle'), 'Pip', NOW)?.kind)
      .toBe('idle');
    const cleared = bridgeReactionFor('alert', state('idle'), 'Pip', NOW);
    expect(cleared?.text).toContain('All clear');
    expect(bridgeReactionFor('connecting', state('idle'), 'Pip', NOW)).toBeNull();
  });

  it('names the pet in the bubble text', () => {
    expect(bridgeReactionFor('idle', state('working'), 'Pip', NOW)?.text)
      .toContain('Pip');
  });
});

class FakeScheduler implements Scheduler {
  fn: (() => void) | null = null;
  set(fn: () => void): unknown {
    this.fn = fn;
    return 1;
  }
  clear(): void {
    this.fn = null;
  }
}

describe('BridgeLinkService', () => {
  function harness(files: Record<string, string | null>) {
    const reactions: BridgeReaction[] = [];
    const scheduler = new FakeScheduler();
    const svc = new BridgeLinkService({
      onReaction: (r) => reactions.push(r),
      petName: () => 'Pip',
      candidates: ['state.json'],
      readFile: (p) => files[p] ?? null,
      now: () => NOW,
      scheduler,
    });
    return { svc, reactions, scheduler };
  }
  const body = (s: string) => JSON.stringify({ state: s });

  it('reacts on change, not on repeats', () => {
    const files: Record<string, string | null> = { 'state.json': body('idle') };
    const { svc, reactions } = harness(files);
    svc.pollOnce();
    files['state.json'] = body('working');
    svc.pollOnce();
    svc.pollOnce();
    files['state.json'] = body('idle');
    svc.pollOnce();
    expect(reactions.map((r) => r.kind)).toEqual(['working', 'idle']);
  });

  it('a missing or corrupt file is a quiet no-op, and recovery works', () => {
    const files: Record<string, string | null> = { 'state.json': null };
    const { svc, reactions } = harness(files);
    svc.pollOnce();
    files['state.json'] = '{corrupt';
    svc.pollOnce();
    files['state.json'] = body('alert');
    svc.pollOnce();
    expect(reactions.map((r) => r.kind)).toEqual(['alert']);
  });

  it('start polls immediately and on the scheduler; stop halts', () => {
    const files: Record<string, string | null> = { 'state.json': body('working') };
    const { svc, reactions, scheduler } = harness(files);
    svc.start();
    expect(svc.running).toBe(true);
    expect(reactions.map((r) => r.kind)).toEqual(['working']);
    files['state.json'] = body('idle');
    scheduler.fn?.();
    expect(reactions.map((r) => r.kind)).toEqual(['working', 'idle']);
    svc.stop();
    expect(svc.running).toBe(false);
  });
});

describe('bridgeStateCandidates', () => {
  it('puts the env override first', () => {
    const list = bridgeStateCandidates(
      { DRABBIT_BRIDGE_STATE_FILE: 'X:\\custom\\display-state.json' },
      'C:\\Users\\test',
    );
    expect(list[0]).toBe('X:\\custom\\display-state.json');
    expect(list.length).toBe(3);
  });
});
