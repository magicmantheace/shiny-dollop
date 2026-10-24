// In-memory FakeAidmApi for renderer tests. Dice and checks run through
// the real shared engine (shared/dice.ts + ruleset.ts) over a per-campaign
// stream state, so the UI is exercised against genuine deterministic
// behavior, not stubbed numbers.
import { rollNotation } from '../../shared/dice';
import { aidmError, AIDM_ERROR_CODES } from '../../shared/errors';
import { hashSeed } from '../../shared/prng';
import { checkSucceeds, defaultStats, difficultyTarget } from '../../shared/ruleset';
import type {
  AidmApi,
  Campaign,
  Character,
  Encounter,
  LogEntry,
  MemoryEntry,
  NarrationSettings,
} from '../../shared/types';

let counter = 0;
function nextId(prefix: string): string {
  counter += 1;
  return `${prefix}-${counter}`;
}
function ts(): string {
  return new Date(Date.UTC(2026, 9, 23, 20, 0, counter)).toISOString();
}

export class FakeAidmApi implements AidmApi {
  readonly campaigns = new Map<string, Campaign>();
  readonly characters = new Map<string, Character>();
  readonly sessions = new Map<string, { id: string; campaignId: string; title: string; notes: string; startedAt: string; endedAt: string | null }>();
  readonly encounters = new Map<string, Encounter>();
  readonly memory = new Map<string, MemoryEntry>();
  readonly log: LogEntry[] = [];
  settings: NarrationSettings = { narrator: 'mock', endpoint: 'http://127.0.0.1:11434', model: '' };
  readonly calls: string[] = [];

  private campaign(id: string): Campaign {
    const c = this.campaigns.get(id);
    if (!c) throw aidmError(AIDM_ERROR_CODES.CAMPAIGN_NOT_FOUND, 'Campaign not found.');
    return c;
  }

  private append(campaignId: string, kind: LogEntry['kind'], text: string, detail: Record<string, unknown> | null, sessionId: string | null = null): LogEntry {
    const entry: LogEntry = {
      id: nextId('log'),
      campaignId,
      sessionId,
      seq: this.log.filter((e) => e.campaignId === campaignId).length + 1,
      kind,
      text,
      detail,
      narration: null,
      narrationSource: null,
      createdAt: ts(),
    };
    this.log.push(entry);
    return entry;
  }

  async campaignsList(): Promise<Campaign[]> {
    this.calls.push('campaignsList');
    return [...this.campaigns.values()];
  }

  async campaignsCreate(input: { name: string; setting?: string; seed?: string }): Promise<Campaign> {
    if (!input.name.trim()) throw aidmError(AIDM_ERROR_CODES.INPUT_INVALID, 'Campaign name must not be empty.');
    const seed = input.seed ?? 'fake-seed';
    const campaign: Campaign = {
      id: nextId('camp'),
      name: input.name,
      setting: input.setting ?? '',
      seed,
      diceState: hashSeed(seed),
      createdAt: ts(),
      updatedAt: ts(),
    };
    this.campaigns.set(campaign.id, campaign);
    this.append(campaign.id, 'system', `Campaign "${campaign.name}" created.`, null);
    return campaign;
  }

  async campaignsGet(id: string): Promise<Campaign> {
    return this.campaign(id);
  }

  async campaignsDelete(id: string): Promise<void> {
    this.campaigns.delete(id);
  }

  async sessionsList(campaignId: string): Promise<never[]> {
    return [...this.sessions.values()].filter((s) => s.campaignId === campaignId) as never[];
  }

  async sessionsCreate(campaignId: string, input: { title: string }) {
    const session = {
      id: nextId('sess'),
      campaignId,
      title: input.title,
      notes: '',
      startedAt: ts(),
      endedAt: null,
    };
    this.sessions.set(session.id, session);
    return session;
  }

  async sessionsUpdateNotes(sessionId: string, notes: string) {
    const s = this.sessions.get(sessionId);
    if (!s) throw aidmError(AIDM_ERROR_CODES.SESSION_NOT_FOUND, 'Session not found.');
    s.notes = notes;
    return s;
  }

  async sessionsEnd(sessionId: string) {
    const s = this.sessions.get(sessionId);
    if (!s) throw aidmError(AIDM_ERROR_CODES.SESSION_NOT_FOUND, 'Session not found.');
    s.endedAt = ts();
    return s;
  }

  async charactersList(campaignId: string): Promise<Character[]> {
    return [...this.characters.values()].filter((c) => c.campaignId === campaignId);
  }

  async charactersCreate(campaignId: string, input: Parameters<AidmApi['charactersCreate']>[1]): Promise<Character> {
    const character: Character = {
      id: nextId('char'),
      campaignId,
      kind: input.kind,
      name: input.name,
      archetype: input.archetype ?? '',
      stats: { ...defaultStats(), ...(input.stats ?? {}) },
      hpMax: input.hpMax ?? 10,
      hpCurrent: input.hpCurrent ?? input.hpMax ?? 10,
      inventory: input.inventory ?? [],
      notes: input.notes ?? '',
      createdAt: ts(),
      updatedAt: ts(),
    };
    this.characters.set(character.id, character);
    return character;
  }

  async charactersUpdate(id: string, patch: Parameters<AidmApi['charactersUpdate']>[1]): Promise<Character> {
    const c = this.characters.get(id);
    if (!c) throw aidmError(AIDM_ERROR_CODES.CHARACTER_NOT_FOUND, 'Character not found.');
    Object.assign(c, patch);
    if (patch.stats) c.stats = { ...c.stats, ...patch.stats };
    return c;
  }

  async charactersDelete(id: string): Promise<void> {
    this.characters.delete(id);
  }

  async diceRoll(campaignId: string, req: Parameters<AidmApi['diceRoll']>[1]) {
    const campaign = this.campaign(campaignId);
    const outcome = rollNotation(req.notation, campaign.diceState);
    campaign.diceState = outcome.stateAfter;
    const entry = this.append(campaignId, 'roll', `Rolled ${outcome.notation}: = ${outcome.total}`, { outcome }, req.sessionId ?? null);
    return { outcome, entry };
  }

  async checkRoll(campaignId: string, req: Parameters<AidmApi['checkRoll']>[1]) {
    const campaign = this.campaign(campaignId);
    const character = this.characters.get(req.characterId);
    if (!character) throw aidmError(AIDM_ERROR_CODES.CHARACTER_NOT_FOUND, 'Character not found.');
    const target = difficultyTarget(req.difficulty);
    const base = rollNotation('2d6', campaign.diceState);
    campaign.diceState = base.stateAfter;
    const attr = character.stats[req.attribute];
    const outcome = { ...base, notation: `2d6+${attr}`, modifier: attr, total: base.dice.reduce((s, d) => s + d, 0) + attr };
    const succeeded = checkSucceeds(outcome.total, target);
    const entry = this.append(campaignId, 'check', `${character.name} check — ${succeeded ? 'SUCCESS' : 'FAILURE'}`, { outcome }, req.sessionId ?? null);
    return { outcome, target, succeeded, entry };
  }

  async logList(campaignId: string): Promise<LogEntry[]> {
    return this.log.filter((e) => e.campaignId === campaignId);
  }

  async logAddNote(campaignId: string, text: string, sessionId?: string | null): Promise<LogEntry> {
    return this.append(campaignId, 'note', text, null, sessionId ?? null);
  }

  async encountersStart(campaignId: string, req: Parameters<AidmApi['encountersStart']>[1]): Promise<Encounter> {
    const campaign = this.campaign(campaignId);
    const combatants = req.characterIds.map((id) => {
      const character = this.characters.get(id);
      if (!character) throw aidmError(AIDM_ERROR_CODES.CHARACTER_NOT_FOUND, 'Character not found.');
      const base = rollNotation('2d6', campaign.diceState);
      campaign.diceState = base.stateAfter;
      const initiative = { ...base, modifier: character.stats.agility, total: base.dice.reduce((s, d) => s + d, 0) + character.stats.agility };
      return { characterId: id, name: character.name, initiative, initiativeTotal: initiative.total };
    });
    combatants.sort((a, b) => b.initiativeTotal - a.initiativeTotal);
    const encounter: Encounter = {
      id: nextId('enc'),
      campaignId,
      sessionId: req.sessionId ?? null,
      name: req.name,
      status: 'active',
      combatants,
      turnIndex: 0,
      round: 1,
      createdAt: ts(),
      endedAt: null,
    };
    this.encounters.set(encounter.id, encounter);
    this.append(campaignId, 'encounter', `Encounter "${req.name}" started.`, null, req.sessionId ?? null);
    return encounter;
  }

  async encountersGetActive(campaignId: string): Promise<Encounter | null> {
    return [...this.encounters.values()].find((e) => e.campaignId === campaignId && e.status === 'active') ?? null;
  }

  async encountersAdvanceTurn(encounterId: string): Promise<Encounter> {
    const e = this.encounters.get(encounterId);
    if (!e) throw aidmError(AIDM_ERROR_CODES.ENCOUNTER_NOT_FOUND, 'Encounter not found.');
    e.turnIndex += 1;
    if (e.turnIndex >= e.combatants.length) {
      e.turnIndex = 0;
      e.round += 1;
    }
    return e;
  }

  private hp(encounterId: string, req: { characterId: string; amount: number }, kind: 'damage' | 'heal'): Encounter {
    const e = this.encounters.get(encounterId);
    if (!e) throw aidmError(AIDM_ERROR_CODES.ENCOUNTER_NOT_FOUND, 'Encounter not found.');
    const c = this.characters.get(req.characterId);
    if (!c) throw aidmError(AIDM_ERROR_CODES.CHARACTER_NOT_FOUND, 'Character not found.');
    c.hpCurrent = kind === 'damage' ? Math.max(0, c.hpCurrent - req.amount) : Math.min(c.hpMax, c.hpCurrent + req.amount);
    this.append(e.campaignId, kind, `${c.name} ${kind} ${req.amount}`, null, e.sessionId);
    return e;
  }

  async encountersApplyDamage(encounterId: string, req: Parameters<AidmApi['encountersApplyDamage']>[1]): Promise<Encounter> {
    return this.hp(encounterId, req, 'damage');
  }

  async encountersApplyHeal(encounterId: string, req: Parameters<AidmApi['encountersApplyHeal']>[1]): Promise<Encounter> {
    return this.hp(encounterId, req, 'heal');
  }

  async encountersEnd(encounterId: string): Promise<Encounter> {
    const e = this.encounters.get(encounterId);
    if (!e) throw aidmError(AIDM_ERROR_CODES.ENCOUNTER_NOT_FOUND, 'Encounter not found.');
    e.status = 'ended';
    e.endedAt = ts();
    return e;
  }

  async memoryList(campaignId: string): Promise<MemoryEntry[]> {
    return [...this.memory.values()].filter((m) => m.campaignId === campaignId);
  }

  async memoryCreate(campaignId: string, input: Parameters<AidmApi['memoryCreate']>[1]): Promise<MemoryEntry> {
    const entry: MemoryEntry = {
      id: nextId('mem'),
      campaignId,
      kind: input.kind,
      title: input.title,
      body: input.body ?? '',
      tags: input.tags ?? [],
      source: 'manual',
      createdAt: ts(),
      updatedAt: ts(),
    };
    this.memory.set(entry.id, entry);
    return entry;
  }

  async memoryUpdate(id: string, patch: Parameters<AidmApi['memoryUpdate']>[1]): Promise<MemoryEntry> {
    const m = this.memory.get(id);
    if (!m) throw aidmError(AIDM_ERROR_CODES.MEMORY_NOT_FOUND, 'Memory not found.');
    Object.assign(m, patch);
    return m;
  }

  async memoryDelete(id: string): Promise<void> {
    this.memory.delete(id);
  }

  async memorySearch(campaignId: string, query: string): Promise<MemoryEntry[]> {
    const q = query.trim().toLowerCase();
    const all = await this.memoryList(campaignId);
    if (!q) return all;
    return all.filter((m) => m.title.toLowerCase().includes(q) || m.body.toLowerCase().includes(q));
  }

  async narrate(logEntryId: string) {
    const entry = this.log.find((e) => e.id === logEntryId);
    if (!entry) throw aidmError(AIDM_ERROR_CODES.LOG_ENTRY_NOT_FOUND, 'Log entry not found.');
    entry.narration = `Flavor for: ${entry.text}`;
    entry.narrationSource = 'mock';
    return { entry, source: 'mock' };
  }

  async settingsGet(): Promise<NarrationSettings> {
    return this.settings;
  }

  async settingsUpdate(settings: NarrationSettings): Promise<NarrationSettings> {
    this.settings = settings;
    return settings;
  }

  async exportCampaign(campaignId: string): Promise<string> {
    const campaign = this.campaign(campaignId);
    return JSON.stringify({ format: 'ai-dungeon-master/campaign', formatVersion: '1.0.0', campaign }, null, 2);
  }

  async importCampaign(text: string): Promise<Campaign> {
    const parsed = JSON.parse(text) as { campaign: Campaign };
    const copy: Campaign = { ...parsed.campaign, id: nextId('camp') };
    this.campaigns.set(copy.id, copy);
    return copy;
  }

  async importWorldbuilding(campaignId: string, text: string) {
    const parsed = JSON.parse(text) as { entities: Array<{ name: string; type: string }> };
    for (const e of parsed.entities) {
      await this.memoryCreate(campaignId, { kind: e.type === 'character' ? 'npc' : e.type === 'location' ? 'location' : 'fact', title: e.name });
    }
    return { createdMemoryEntries: parsed.entities.length, detail: `${parsed.entities.length} imported.` };
  }

  async importDungeonManifest(campaignId: string, text: string) {
    const parsed = JSON.parse(text) as { name: string };
    await this.memoryCreate(campaignId, { kind: 'location', title: parsed.name });
    return { createdMemoryEntries: 1, detail: `Dungeon "${parsed.name}" imported.` };
  }
}

export function installFakeAidm(): FakeAidmApi {
  const fake = new FakeAidmApi();
  (window as unknown as Record<string, unknown>).aidm = fake;
  return fake;
}
