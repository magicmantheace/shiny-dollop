// Hermetic fake SpectatorApi for renderer tests.

import type { Descender, LedgerEvent } from '../../shared/contract';
import type { ConnectionStatus, Prefs, SpectatorApi } from '../../shared/types';

export function makeEvent(id: string, tick: number, type: string, actors: string[], summary: string): LedgerEvent {
  return {
    id, descent_id: 'descent-fixture-001', stratum_number: 3, tick, event_type: type, summary,
    actor_ids: actors, sector_id: 'sector-ash-gate',
    semantic: { importance_score: 0.4, rarity_score: 0.1, danger_level: 0.2, reversal: false, relationship_impact: 0, audience_interest_tags: [], causal_parent_ids: [] },
    canonical: true,
  };
}

export const mira: Descender = {
  descender_id: 'mira-vane', status: 'active', health: 82, current_stratum: 3, current_sector_id: 'sector-ash-gate',
  current_party_id: 'party-ember-pact', current_objective: 'Reach the Stratum 3 exit', level: 6, experience: 1840,
  specialization: 'pathfinder', abilities: ['survey'], kills: 4, encounters_survived: 11, injuries: [], inventory: [],
  equipment: {}, public_profile: { current_goal: 'Map the ash warrens', last_action: 'survey', decision_count: 57 },
  relationships: [{ target_id: 'ossian-rell', trust: 0.8, respect: 0.7, rivalry: 0.1, familiarity: 0.9 }],
};

export const ossian: Descender = {
  ...mira, descender_id: 'ossian-rell', current_objective: 'Guard the party flank',
  relationships: [{ target_id: 'mira-vane', trust: 0.9, respect: 0.8, rivalry: 0, familiarity: 0.9 }],
};

export const partyEvent = makeEvent('evt-000002', 1184, 'PARTY_FORMED', ['mira-vane', 'ossian-rell'], 'Mira Vane formed the Ember Pact.');
export const damageEvent = makeEvent('evt-000100', 1231, 'DESCENDER_DAMAGED', ['mira-vane'], 'Mira Vane was damaged by a falling bell clapper.');

export class FakeSpectator implements SpectatorApi {
  status: ConnectionStatus;
  prefs: Prefs = { baseUrl: 'http://127.0.0.1:8000', followedDescenderIds: [] };
  private statusListeners = new Set<(s: ConnectionStatus) => void>();

  constructor(mode: 'live' | 'demo' = 'demo') {
    this.status = {
      state: 'connected', mode,
      baseUrl: mode === 'demo' ? 'demo://fixture' : 'http://127.0.0.1:8000',
      message: mode === 'demo' ? 'DEMO MODE — showing invented fixture data.' : 'Connected.',
      descentId: 'descent-fixture-001', tick: 1240, reconnectAttempts: 0,
    };
  }

  async getStatus(): Promise<ConnectionStatus> { return this.status; }
  async connectLive(baseUrl: string): Promise<ConnectionStatus> {
    this.status = { ...this.status, state: 'connected', mode: 'live', baseUrl };
    return this.status;
  }
  async connectDemo(): Promise<ConnectionStatus> {
    this.status = { ...this.status, state: 'connected', mode: 'demo', baseUrl: 'demo://fixture' };
    return this.status;
  }
  async disconnect(): Promise<ConnectionStatus> {
    this.status = { ...this.status, state: 'disconnected' };
    return this.status;
  }
  async getDescent(): Promise<null> { return null; }
  async listDescenders(): Promise<Descender[]> { return [mira, ossian]; }
  async getProfile(id: string): Promise<Descender> { return id === 'mira-vane' ? mira : ossian; }
  async getHistory(id: string): Promise<LedgerEvent[]> { return id === 'mira-vane' ? [damageEvent] : []; }
  async search(_query: string): Promise<{ query: string; descenders: Descender[]; events: LedgerEvent[] }> {
    return { query: _query, descenders: [mira], events: [] };
  }
  async listParties(): Promise<Array<{ id: string; active: boolean; leader_descender_id: string | null; member_descender_ids: string[]; cohesion: number; loot_policy: string }>> {
    return [{ id: 'party-ember-pact', active: true, leader_descender_id: 'mira-vane', member_descender_ids: ['mira-vane', 'ossian-rell'], cohesion: 0.82, loot_policy: 'need_before_greed' }];
  }
  async getFeed(): Promise<{ events: LedgerEvent[]; cursorTick: number | null; droppedCount: number; bufferedCount: number }> {
    return { events: [partyEvent, damageEvent], cursorTick: 1231, droppedCount: 0, bufferedCount: 2 };
  }
  async getReplay(): Promise<LedgerEvent[]> { return [damageEvent]; }
  async getHighlights(): Promise<LedgerEvent[]> {
    return this.prefs.followedDescenderIds.includes('mira-vane') ? [partyEvent, damageEvent] : [];
  }
  async getPrefs(): Promise<Prefs> { return this.prefs; }
  async follow(id: string): Promise<Prefs> {
    this.prefs = { ...this.prefs, followedDescenderIds: [...this.prefs.followedDescenderIds, id] };
    return this.prefs;
  }
  async unfollow(id: string): Promise<Prefs> {
    this.prefs = { ...this.prefs, followedDescenderIds: this.prefs.followedDescenderIds.filter((x) => x !== id) };
    return this.prefs;
  }
  async exportPrefs(): Promise<{ formatVersion: string; prefs: Prefs }> { return { formatVersion: '1.0.0', prefs: this.prefs }; }
  async importPrefs(): Promise<Prefs> { return this.prefs; }
  onStatusChanged(listener: (s: ConnectionStatus) => void): () => void {
    this.statusListeners.add(listener);
    return () => this.statusListeners.delete(listener);
  }
  onFeedChanged(): () => void { return () => undefined; }
}
