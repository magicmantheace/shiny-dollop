// CampaignService: every AidmApi operation, implemented against the
// store. The deterministic dice stream lives on the campaign row: each
// roll reads campaign.diceState, rolls purely, persists the new state,
// and appends an immutable log entry carrying the full RollOutcome —
// so the entire history can be replayed and audited from the seed.
import { randomUUID } from 'node:crypto';
import type { DatabaseSync } from 'node:sqlite';
import { parseDiceNotation, rollFromState, rollNotation } from '../../shared/dice.js';
import { AIDM_ERROR_CODES, aidmError } from '../../shared/errors.js';
import {
  buildCampaignBundle,
  dungeonManifestToMemoryBody,
  parseCampaignBundle,
  parseDungeonManifest,
  parseWorldbuildingBackup,
  worldbuildingMemoryKind,
} from '../../shared/export.js';
import { hashSeed } from '../../shared/prng.js';
import {
  ATTRIBUTE_MAX,
  ATTRIBUTE_MIN,
  checkSucceeds,
  defaultStats,
  difficultyTarget,
} from '../../shared/ruleset.js';
import type {
  Campaign,
  CampaignBundle,
  CampaignInput,
  Character,
  CharacterInput,
  CharacterPatch,
  CheckRequest,
  CheckResponse,
  Encounter,
  EncounterStartRequest,
  HpChangeRequest,
  ImportSummary,
  LogEntry,
  LogKind,
  MemoryEntry,
  MemoryInput,
  MemoryPatch,
  NarrationResponse,
  NarrationSettings,
  RollRequest,
  RollResponse,
  Session,
  Stats,
} from '../../shared/types.js';
import { MockNarrator, createNarrator, isLoopbackUrl } from './narrator.js';
import * as store from './store.js';

const MAX_TEXT = 100_000;

function newId(): string {
  return randomUUID();
}

function requireText(value: string, field: string, max = 500): string {
  if (typeof value !== 'string' || value.trim().length === 0) {
    throw aidmError(AIDM_ERROR_CODES.INPUT_INVALID, `${field} must not be empty.`);
  }
  if (value.length > max) {
    throw aidmError(AIDM_ERROR_CODES.INPUT_TOO_LARGE, `${field} exceeds ${max} characters.`);
  }
  return value;
}

function clampStats(input: Partial<Stats> | undefined): Stats {
  const base = defaultStats();
  if (!input) return base;
  for (const key of Object.keys(base) as Array<keyof Stats>) {
    const value = input[key];
    if (value === undefined) continue;
    if (!Number.isInteger(value) || value < ATTRIBUTE_MIN || value > ATTRIBUTE_MAX) {
      throw aidmError(
        AIDM_ERROR_CODES.INPUT_INVALID,
        `Stat ${key} must be an integer between ${ATTRIBUTE_MIN} and ${ATTRIBUTE_MAX}.`,
      );
    }
    base[key] = value;
  }
  return base;
}

export class CampaignService {
  constructor(private readonly db: DatabaseSync) {}

  // ---------- campaigns ----------

  async campaignsList(): Promise<Campaign[]> {
    return store.listCampaigns(this.db);
  }

  async campaignsCreate(input: CampaignInput): Promise<Campaign> {
    const name = requireText(input.name, 'Campaign name', 200);
    const setting = input.setting ?? '';
    if (setting.length > MAX_TEXT) {
      throw aidmError(AIDM_ERROR_CODES.INPUT_TOO_LARGE, 'Setting is too long.');
    }
    const seed =
      input.seed !== undefined && input.seed.trim().length > 0
        ? input.seed.trim()
        : `campaign-${newId()}`;
    if (seed.length > 200) {
      throw aidmError(AIDM_ERROR_CODES.INPUT_TOO_LARGE, 'Seed exceeds 200 characters.');
    }
    const now = store.nowIso();
    const campaign: Campaign = {
      id: newId(),
      name,
      setting,
      seed,
      diceState: hashSeed(seed),
      createdAt: now,
      updatedAt: now,
    };
    store.insertCampaign(this.db, campaign);
    this.appendLog(campaign, null, 'system', `Campaign "${name}" created (dice seed "${seed}").`, {
      seed,
    });
    return store.getCampaign(this.db, campaign.id) ?? campaign;
  }

  async campaignsGet(id: string): Promise<Campaign> {
    return this.requireCampaign(id);
  }

  async campaignsDelete(id: string): Promise<void> {
    this.requireCampaign(id);
    store.deleteCampaign(this.db, id);
  }

  private requireCampaign(id: string): Campaign {
    const campaign = store.getCampaign(this.db, id);
    if (!campaign) {
      throw aidmError(AIDM_ERROR_CODES.CAMPAIGN_NOT_FOUND, `Campaign ${id} was not found.`);
    }
    return campaign;
  }

  private touchCampaign(campaign: Campaign): Campaign {
    const updated = { ...campaign, updatedAt: store.nowIso() };
    store.updateCampaign(this.db, updated);
    return updated;
  }

  // ---------- log ----------

  private appendLog(
    campaign: Campaign,
    sessionId: string | null,
    kind: LogKind,
    text: string,
    detail: Record<string, unknown> | null,
  ): LogEntry {
    const entry: LogEntry = {
      id: newId(),
      campaignId: campaign.id,
      sessionId,
      seq: store.nextLogSeq(this.db, campaign.id),
      kind,
      text,
      detail,
      narration: null,
      narrationSource: null,
      createdAt: store.nowIso(),
    };
    return store.insertLogEntry(this.db, entry);
  }

  async logList(campaignId: string, sessionId?: string | null): Promise<LogEntry[]> {
    this.requireCampaign(campaignId);
    return store.listLogEntries(this.db, campaignId, sessionId);
  }

  async logAddNote(
    campaignId: string,
    text: string,
    sessionId?: string | null,
  ): Promise<LogEntry> {
    const campaign = this.requireCampaign(campaignId);
    requireText(text, 'Note text', MAX_TEXT);
    const validSessionId = this.requireSessionInCampaign(sessionId, campaignId);
    return this.appendLog(campaign, validSessionId, 'note', text, null);
  }

  // ---------- sessions ----------

  async sessionsList(campaignId: string): Promise<Session[]> {
    this.requireCampaign(campaignId);
    return store.listSessions(this.db, campaignId);
  }

  async sessionsCreate(campaignId: string, input: { title: string }): Promise<Session> {
    this.requireCampaign(campaignId);
    const title = requireText(input.title, 'Session title', 200);
    const session: Session = {
      id: newId(),
      campaignId,
      title,
      notes: '',
      startedAt: store.nowIso(),
      endedAt: null,
    };
    store.insertSession(this.db, session);
    return session;
  }

  private requireSession(id: string): Session {
    const session = store.getSession(this.db, id);
    if (!session) {
      throw aidmError(AIDM_ERROR_CODES.SESSION_NOT_FOUND, `Session ${id} was not found.`);
    }
    return session;
  }

  /**
   * Validate an optional session reference for a write into `campaignId`
   * BEFORE anything is persisted. A session from another campaign (or a
   * nonexistent one) is rejected with SESSION_NOT_FOUND: persisting it
   * would attribute rolls/notes/encounters to a session the target
   * campaign does not own — and would make that campaign's own export
   * unimportable, since the bundle cannot contain the foreign session.
   * Returns the validated session id (or null).
   */
  private requireSessionInCampaign(
    sessionId: string | null | undefined,
    campaignId: string,
  ): string | null {
    if (sessionId === null || sessionId === undefined) return null;
    const session = store.getSession(this.db, sessionId);
    if (!session || session.campaignId !== campaignId) {
      throw aidmError(
        AIDM_ERROR_CODES.SESSION_NOT_FOUND,
        `Session ${sessionId} is not a session of this campaign.`,
      );
    }
    return sessionId;
  }

  async sessionsUpdateNotes(sessionId: string, notes: string): Promise<Session> {
    const session = this.requireSession(sessionId);
    if (typeof notes !== 'string' || notes.length > MAX_TEXT) {
      throw aidmError(AIDM_ERROR_CODES.INPUT_TOO_LARGE, 'Session notes are too long.');
    }
    const updated = { ...session, notes };
    store.updateSession(this.db, updated);
    return updated;
  }

  async sessionsEnd(sessionId: string): Promise<Session> {
    const session = this.requireSession(sessionId);
    const updated = { ...session, endedAt: session.endedAt ?? store.nowIso() };
    store.updateSession(this.db, updated);
    return updated;
  }

  // ---------- characters ----------

  async charactersList(campaignId: string): Promise<Character[]> {
    this.requireCampaign(campaignId);
    return store.listCharacters(this.db, campaignId);
  }

  async charactersCreate(campaignId: string, input: CharacterInput): Promise<Character> {
    this.requireCampaign(campaignId);
    const name = requireText(input.name, 'Character name', 200);
    const hpMax = input.hpMax ?? 10;
    if (!Number.isInteger(hpMax) || hpMax < 1 || hpMax > 10_000) {
      throw aidmError(AIDM_ERROR_CODES.INPUT_INVALID, 'Max HP must be an integer 1..10000.');
    }
    const hpCurrent = input.hpCurrent ?? hpMax;
    if (!Number.isInteger(hpCurrent) || hpCurrent < 0 || hpCurrent > hpMax) {
      throw aidmError(
        AIDM_ERROR_CODES.INPUT_INVALID,
        'Current HP must be an integer between 0 and max HP.',
      );
    }
    const inventory = (input.inventory ?? []).map((item) => requireText(item, 'Inventory item', 200));
    if (inventory.length > 200) {
      throw aidmError(AIDM_ERROR_CODES.INPUT_TOO_LARGE, 'Inventory is limited to 200 items.');
    }
    const now = store.nowIso();
    const character: Character = {
      id: newId(),
      campaignId,
      kind: input.kind,
      name,
      archetype: input.archetype ?? '',
      stats: clampStats(input.stats),
      hpCurrent,
      hpMax,
      inventory,
      notes: input.notes ?? '',
      createdAt: now,
      updatedAt: now,
    };
    store.insertCharacter(this.db, character);
    return character;
  }

  private requireCharacter(id: string): Character {
    const character = store.getCharacter(this.db, id);
    if (!character) {
      throw aidmError(AIDM_ERROR_CODES.CHARACTER_NOT_FOUND, `Character ${id} was not found.`);
    }
    return character;
  }

  async charactersUpdate(id: string, patch: CharacterPatch): Promise<Character> {
    const character = this.requireCharacter(id);
    const next: Character = { ...character, updatedAt: store.nowIso() };
    if (patch.name !== undefined) next.name = requireText(patch.name, 'Character name', 200);
    if (patch.archetype !== undefined) next.archetype = patch.archetype;
    if (patch.kind !== undefined) next.kind = patch.kind;
    if (patch.notes !== undefined) next.notes = patch.notes;
    if (patch.stats !== undefined) next.stats = clampStats({ ...character.stats, ...patch.stats });
    if (patch.hpMax !== undefined) {
      if (!Number.isInteger(patch.hpMax) || patch.hpMax < 1 || patch.hpMax > 10_000) {
        throw aidmError(AIDM_ERROR_CODES.INPUT_INVALID, 'Max HP must be an integer 1..10000.');
      }
      next.hpMax = patch.hpMax;
    }
    if (patch.hpCurrent !== undefined) {
      if (!Number.isInteger(patch.hpCurrent) || patch.hpCurrent < 0) {
        throw aidmError(AIDM_ERROR_CODES.INPUT_INVALID, 'Current HP must be a non-negative integer.');
      }
      next.hpCurrent = patch.hpCurrent;
    }
    // Direct sheet edits are allowed outside combat, but HP is clamped to
    // the sheet's max; combat damage/healing goes through encounters so
    // it is always logged.
    next.hpCurrent = Math.min(next.hpCurrent, next.hpMax);
    if (patch.inventory !== undefined) {
      next.inventory = patch.inventory.map((item) => requireText(item, 'Inventory item', 200));
    }
    store.updateCharacter(this.db, next);
    return next;
  }

  async charactersDelete(id: string): Promise<void> {
    const character = this.requireCharacter(id);
    // A combatant in an active encounter must not be deleted out from
    // under the turn tracker: the encounter would keep referencing the
    // character, damage/healing would fail with CHARACTER_NOT_FOUND,
    // and the character's HP would be lost. End the encounter first.
    const active = store
      .listEncounters(this.db, character.campaignId)
      .find((e) => e.status === 'active' && e.combatants.some((c) => c.characterId === id));
    if (active) {
      throw aidmError(
        AIDM_ERROR_CODES.INPUT_INVALID,
        `${character.name} is a combatant in the active encounter "${active.name}". End the encounter before deleting this character.`,
      );
    }
    store.deleteCharacter(this.db, id);
  }

  // ---------- dice & checks (the authoritative rules engine) ----------

  async diceRoll(campaignId: string, req: RollRequest): Promise<RollResponse> {
    const campaign = this.requireCampaign(campaignId);
    // Validate the session BEFORE rolling: a rejected roll must not
    // advance the campaign's dice stream or write a log entry.
    const sessionId = this.requireSessionInCampaign(req.sessionId, campaignId);
    const spec = parseDiceNotation(req.notation); // throws DICE_NOTATION_INVALID
    const outcome = rollFromState(spec, campaign.diceState);
    this.touchCampaign({ ...campaign, diceState: outcome.stateAfter });
    const label = req.label?.trim() ? ` — ${req.label.trim()}` : '';
    const entry = this.appendLog(
      campaign,
      sessionId,
      'roll',
      `Rolled ${outcome.notation}${label}: [${outcome.dice.join(', ')}]${outcome.modifier !== 0 ? ` ${outcome.modifier > 0 ? '+' : '−'} ${Math.abs(outcome.modifier)}` : ''} = ${outcome.total}`,
      { outcome },
    );
    return { outcome, entry };
  }

  async checkRoll(campaignId: string, req: CheckRequest): Promise<CheckResponse> {
    const campaign = this.requireCampaign(campaignId);
    const character = this.requireCharacter(req.characterId);
    if (character.campaignId !== campaignId) {
      throw aidmError(AIDM_ERROR_CODES.CHARACTER_NOT_FOUND, 'Character is not in this campaign.');
    }
    const sessionId = this.requireSessionInCampaign(req.sessionId, campaignId);
    const target = difficultyTarget(req.difficulty);
    const attributeValue = character.stats[req.attribute];
    const outcome = rollNotation('2d6', campaign.diceState);
    const withAttr = {
      ...outcome,
      notation: `2d6+${attributeValue}`,
      spec: { ...outcome.spec, modifier: attributeValue },
      modifier: attributeValue,
      total: outcome.dice.reduce((s, d) => s + d, 0) + attributeValue,
    };
    this.touchCampaign({ ...campaign, diceState: outcome.stateAfter });
    const succeeded = checkSucceeds(withAttr.total, target);
    const entry = this.appendLog(
      campaign,
      sessionId,
      'check',
      `${character.name} ${req.attribute} check (${req.difficulty}, target ${target}): [${withAttr.dice.join(', ')}] + ${attributeValue} = ${withAttr.total} — ${succeeded ? 'SUCCESS' : 'FAILURE'}`,
      { outcome: withAttr, target, succeeded, characterId: character.id, attribute: req.attribute },
    );
    return { outcome: withAttr, target, succeeded, entry };
  }

  // ---------- encounters ----------

  async encountersStart(campaignId: string, req: EncounterStartRequest): Promise<Encounter> {
    const campaign = this.requireCampaign(campaignId);
    // Validate the session BEFORE rolling initiative: a rejected start
    // must not advance the dice stream or write any log entries.
    const sessionId = this.requireSessionInCampaign(req.sessionId, campaignId);
    const name = requireText(req.name, 'Encounter name', 200);
    if (!Array.isArray(req.characterIds) || req.characterIds.length === 0) {
      throw aidmError(AIDM_ERROR_CODES.INPUT_INVALID, 'An encounter needs at least one character.');
    }
    if (req.characterIds.length > 50) {
      throw aidmError(AIDM_ERROR_CODES.INPUT_TOO_LARGE, 'Encounters are limited to 50 combatants.');
    }
    const existing = store
      .listEncounters(this.db, campaignId)
      .find((e) => e.status === 'active');
    if (existing) {
      throw aidmError(
        AIDM_ERROR_CODES.INPUT_INVALID,
        `Encounter "${existing.name}" is still active. End it before starting another.`,
      );
    }
    // Roll initiative for each combatant from the campaign dice stream:
    // 2d6 + Agility. Every roll is individually logged and replayable.
    let state = campaign.diceState;
    const rolled: Array<{ character: Character; outcome: ReturnType<typeof rollNotation> }> = [];
    for (const characterId of req.characterIds) {
      const character = this.requireCharacter(characterId);
      if (character.campaignId !== campaignId) {
        throw aidmError(AIDM_ERROR_CODES.CHARACTER_NOT_FOUND, 'Character is not in this campaign.');
      }
      const base = rollNotation('2d6', state);
      state = base.stateAfter;
      const outcome = {
        ...base,
        notation: `2d6+${character.stats.agility}`,
        spec: { ...base.spec, modifier: character.stats.agility },
        modifier: character.stats.agility,
        total: base.dice.reduce((s, d) => s + d, 0) + character.stats.agility,
      };
      rolled.push({ character, outcome });
    }
    this.touchCampaign({ ...campaign, diceState: state });
    for (const { character, outcome } of rolled) {
      this.appendLog(
        campaign,
        sessionId,
        'roll',
        `Initiative — ${character.name}: [${outcome.dice.join(', ')}] + ${character.stats.agility} = ${outcome.total}`,
        { outcome, purpose: 'initiative', characterId: character.id },
      );
    }
    const combatants = rolled
      .map(({ character, outcome }) => ({
        characterId: character.id,
        name: character.name,
        initiative: outcome,
        initiativeTotal: outcome.total,
      }))
      .sort((a, b) => {
        if (b.initiativeTotal !== a.initiativeTotal) return b.initiativeTotal - a.initiativeTotal;
        const agilityOf = (id: string): number =>
          rolled.find((r) => r.character.id === id)?.character.stats.agility ?? 0;
        if (agilityOf(b.characterId) !== agilityOf(a.characterId)) {
          return agilityOf(b.characterId) - agilityOf(a.characterId);
        }
        return a.name.localeCompare(b.name);
      });
    const encounter: Encounter = {
      id: newId(),
      campaignId,
      sessionId,
      name,
      status: 'active',
      combatants,
      turnIndex: 0,
      round: 1,
      createdAt: store.nowIso(),
      endedAt: null,
    };
    store.insertEncounter(this.db, encounter);
    this.appendLog(
      campaign,
      sessionId,
      'encounter',
      `Encounter "${name}" started. Order: ${combatants.map((c) => `${c.name} (${c.initiativeTotal})`).join(' → ')}`,
      { encounterId: encounter.id, event: 'start' },
    );
    return encounter;
  }

  private requireEncounter(id: string): Encounter {
    const encounter = store.getEncounter(this.db, id);
    if (!encounter) {
      throw aidmError(AIDM_ERROR_CODES.ENCOUNTER_NOT_FOUND, `Encounter ${id} was not found.`);
    }
    return encounter;
  }

  private requireActiveEncounter(id: string): Encounter {
    const encounter = this.requireEncounter(id);
    if (encounter.status !== 'active') {
      throw aidmError(AIDM_ERROR_CODES.ENCOUNTER_NOT_ACTIVE, `Encounter "${encounter.name}" has ended.`);
    }
    return encounter;
  }

  async encountersGetActive(campaignId: string): Promise<Encounter | null> {
    this.requireCampaign(campaignId);
    return (
      store.listEncounters(this.db, campaignId).find((e) => e.status === 'active') ?? null
    );
  }

  async encountersAdvanceTurn(encounterId: string): Promise<Encounter> {
    const encounter = this.requireActiveEncounter(encounterId);
    let turnIndex = encounter.turnIndex + 1;
    let round = encounter.round;
    if (turnIndex >= encounter.combatants.length) {
      turnIndex = 0;
      round += 1;
    }
    const updated = { ...encounter, turnIndex, round };
    store.updateEncounter(this.db, updated);
    return updated;
  }

  private applyHpChange(
    encounterId: string,
    req: HpChangeRequest,
    kind: 'damage' | 'heal',
  ): Encounter {
    const encounter = this.requireActiveEncounter(encounterId);
    if (!Number.isInteger(req.amount) || req.amount <= 0 || req.amount > 10_000) {
      throw aidmError(AIDM_ERROR_CODES.INPUT_INVALID, 'Amount must be a positive integer.');
    }
    const character = this.requireCharacter(req.characterId);
    if (!encounter.combatants.some((c) => c.characterId === character.id)) {
      throw aidmError(
        AIDM_ERROR_CODES.INPUT_INVALID,
        `${character.name} is not a combatant in this encounter.`,
      );
    }
    const before = character.hpCurrent;
    const after =
      kind === 'damage'
        ? Math.max(0, before - req.amount)
        : Math.min(character.hpMax, before + req.amount);
    store.updateCharacter(this.db, { ...character, hpCurrent: after, updatedAt: store.nowIso() });
    const campaign = this.requireCampaign(encounter.campaignId);
    const note = req.note?.trim() ? ` (${req.note.trim()})` : '';
    this.appendLog(
      campaign,
      encounter.sessionId,
      kind,
      kind === 'damage'
        ? `${character.name} takes ${req.amount} damage${note}: HP ${before} → ${after}${after === 0 ? ' — DOWN' : ''}`
        : `${character.name} heals ${req.amount}${note}: HP ${before} → ${after}`,
      { encounterId: encounter.id, characterId: character.id, amount: req.amount, hpBefore: before, hpAfter: after },
    );
    return encounter;
  }

  async encountersApplyDamage(encounterId: string, req: HpChangeRequest): Promise<Encounter> {
    return this.applyHpChange(encounterId, req, 'damage');
  }

  async encountersApplyHeal(encounterId: string, req: HpChangeRequest): Promise<Encounter> {
    return this.applyHpChange(encounterId, req, 'heal');
  }

  async encountersEnd(encounterId: string): Promise<Encounter> {
    const encounter = this.requireActiveEncounter(encounterId);
    const updated: Encounter = { ...encounter, status: 'ended', endedAt: store.nowIso() };
    store.updateEncounter(this.db, updated);
    const campaign = this.requireCampaign(encounter.campaignId);
    this.appendLog(
      campaign,
      encounter.sessionId,
      'encounter',
      `Encounter "${encounter.name}" ended after ${encounter.round} round(s).`,
      { encounterId: encounter.id, event: 'end' },
    );
    return updated;
  }

  // ---------- memory ----------

  async memoryList(campaignId: string): Promise<MemoryEntry[]> {
    this.requireCampaign(campaignId);
    return store.listMemory(this.db, campaignId);
  }

  async memoryCreate(campaignId: string, input: MemoryInput): Promise<MemoryEntry> {
    this.requireCampaign(campaignId);
    const title = requireText(input.title, 'Memory title', 300);
    const now = store.nowIso();
    const entry: MemoryEntry = {
      id: newId(),
      campaignId,
      kind: input.kind,
      title,
      body: input.body ?? '',
      tags: input.tags ?? [],
      source: 'manual',
      createdAt: now,
      updatedAt: now,
    };
    if (entry.body.length > MAX_TEXT) {
      throw aidmError(AIDM_ERROR_CODES.INPUT_TOO_LARGE, 'Memory body is too long.');
    }
    store.insertMemory(this.db, entry);
    return entry;
  }

  private requireMemory(id: string): MemoryEntry {
    const entry = store.getMemory(this.db, id);
    if (!entry) {
      throw aidmError(AIDM_ERROR_CODES.MEMORY_NOT_FOUND, `Memory entry ${id} was not found.`);
    }
    return entry;
  }

  async memoryUpdate(id: string, patch: MemoryPatch): Promise<MemoryEntry> {
    const entry = this.requireMemory(id);
    const next: MemoryEntry = { ...entry, updatedAt: store.nowIso() };
    if (patch.title !== undefined) next.title = requireText(patch.title, 'Memory title', 300);
    if (patch.body !== undefined) next.body = patch.body;
    if (patch.kind !== undefined) next.kind = patch.kind;
    if (patch.tags !== undefined) next.tags = patch.tags;
    store.updateMemory(this.db, next);
    return next;
  }

  async memoryDelete(id: string): Promise<void> {
    this.requireMemory(id);
    store.deleteMemory(this.db, id);
  }

  async memorySearch(campaignId: string, query: string): Promise<MemoryEntry[]> {
    this.requireCampaign(campaignId);
    const q = query.trim().toLowerCase();
    const all = store.listMemory(this.db, campaignId);
    if (q.length === 0) return all;
    return all.filter(
      (m) =>
        m.title.toLowerCase().includes(q) ||
        m.body.toLowerCase().includes(q) ||
        m.tags.some((t) => t.toLowerCase().includes(q)),
    );
  }

  // ---------- narration (flavor only) ----------

  async settingsGet(): Promise<NarrationSettings> {
    return store.getSettings(this.db);
  }

  async settingsUpdate(settings: NarrationSettings): Promise<NarrationSettings> {
    if (settings.narrator === 'local' && !isLoopbackUrl(settings.endpoint)) {
      throw aidmError(
        AIDM_ERROR_CODES.INPUT_INVALID,
        'Narration endpoint must be a loopback URL (localhost / 127.0.0.1).',
      );
    }
    return store.saveSettings(this.db, settings);
  }

  async narrate(logEntryId: string): Promise<NarrationResponse> {
    const entry = store.getLogEntry(this.db, logEntryId);
    if (!entry) {
      throw aidmError(AIDM_ERROR_CODES.LOG_ENTRY_NOT_FOUND, `Log entry ${logEntryId} was not found.`);
    }
    const campaign = this.requireCampaign(entry.campaignId);
    const settings = store.getSettings(this.db);
    const narrator = createNarrator(settings);
    let text: string;
    let source: string = narrator.source;
    try {
      text = await narrator.narrate({ campaignName: campaign.name, entry });
    } catch {
      // Missing/unreachable local model → graceful fallback to the mock
      // narrator. Narration failure must never break the session.
      text = await new MockNarrator().narrate({ campaignName: campaign.name, entry });
      source = 'mock-fallback';
    }
    const updated = store.attachNarration(this.db, entry, text, source);
    return { entry: updated, source };
  }

  // ---------- export / import ----------

  private collectBundle(campaign: Campaign): CampaignBundle {
    return {
      format: 'ai-dungeon-master/campaign',
      formatVersion: '1.0.0',
      campaign,
      sessions: store.listSessions(this.db, campaign.id),
      characters: store.listCharacters(this.db, campaign.id),
      encounters: store.listEncounters(this.db, campaign.id),
      memory: store.listMemory(this.db, campaign.id),
      log: store.listLogEntries(this.db, campaign.id),
    };
  }

  async exportCampaign(campaignId: string): Promise<string> {
    const campaign = this.requireCampaign(campaignId);
    return buildCampaignBundle(this.collectBundle(campaign));
  }

  async importCampaign(text: string): Promise<Campaign> {
    const bundle = parseCampaignBundle(text);
    // Remap ids when any of them already exist in this database.
    const collides = store.getCampaign(this.db, bundle.campaign.id) !== null;
    const remap = new Map<string, string>();
    const mapId = (id: string): string => {
      if (!collides) return id;
      if (!remap.has(id)) remap.set(id, newId());
      return remap.get(id) as string;
    };
    const campaign: Campaign = { ...bundle.campaign, id: mapId(bundle.campaign.id) };
    store.insertCampaign(this.db, campaign);
    for (const s of bundle.sessions) {
      store.insertSession(this.db, { ...s, id: mapId(s.id), campaignId: campaign.id });
    }
    for (const c of bundle.characters) {
      store.insertCharacter(this.db, { ...c, id: mapId(c.id), campaignId: campaign.id });
    }
    const bundledCharacterIds = new Set(bundle.characters.map((c) => c.id));
    for (const e of bundle.encounters) {
      store.insertEncounter(this.db, {
        ...e,
        id: mapId(e.id),
        campaignId: campaign.id,
        sessionId: e.sessionId ? mapId(e.sessionId) : null,
        // Combatants whose sheet is in the bundle follow the remap. A
        // combatant with NO sheet in the bundle is a historical record
        // from an ended encounter (its character was deleted after the
        // encounter ended): keep its original id as-is instead of
        // remapping it to a fabricated new character id.
        combatants: e.combatants.map((cb) => ({
          ...cb,
          characterId: bundledCharacterIds.has(cb.characterId)
            ? mapId(cb.characterId)
            : cb.characterId,
        })),
      });
    }
    for (const m of bundle.memory) {
      store.insertMemory(this.db, { ...m, id: mapId(m.id), campaignId: campaign.id });
    }
    for (const l of bundle.log) {
      store.insertLogEntry(this.db, {
        ...l,
        id: mapId(l.id),
        campaignId: campaign.id,
        sessionId: l.sessionId ? mapId(l.sessionId) : null,
      });
    }
    return campaign;
  }

  async importWorldbuilding(campaignId: string, text: string): Promise<ImportSummary> {
    const campaign = this.requireCampaign(campaignId);
    const entities = parseWorldbuildingBackup(text);
    let created = 0;
    for (const entity of entities) {
      const kind = worldbuildingMemoryKind(entity.type);
      const roleNote = entity.role ? `Role: ${entity.role}. ` : '';
      const body = [roleNote + entity.description, entity.body].filter((s) => s.length > 0).join('\n\n');
      const now = store.nowIso();
      store.insertMemory(this.db, {
        id: newId(),
        campaignId,
        kind,
        title: entity.name,
        body,
        tags: [...entity.tags, `worldbuilding:${entity.type}`],
        source: 'worldbuilding-import',
        createdAt: now,
        updatedAt: now,
      });
      created += 1;
    }
    this.appendLog(
      campaign,
      null,
      'import',
      `Imported ${created} memory entries from a Worldbuilding Manager project backup.`,
      { source: 'worldbuilding-manager.project', created },
    );
    return {
      createdMemoryEntries: created,
      detail: `${created} worldbuilding entities imported as memory entries.`,
    };
  }

  async importDungeonManifest(campaignId: string, text: string): Promise<ImportSummary> {
    const campaign = this.requireCampaign(campaignId);
    const summary = parseDungeonManifest(text);
    const now = store.nowIso();
    store.insertMemory(this.db, {
      id: newId(),
      campaignId,
      kind: 'location',
      title: summary.name,
      body: dungeonManifestToMemoryBody(summary),
      tags: ['dungeon', `theme:${summary.theme}`, `seed:${summary.seed}`],
      source: 'dungeon-import',
      createdAt: now,
      updatedAt: now,
    });
    this.appendLog(
      campaign,
      null,
      'import',
      `Imported dungeon map "${summary.name}" (${summary.roomCount} rooms) as a location memory entry.`,
      { source: 'procedural-dungeon-designer/map', created: 1 },
    );
    return {
      createdMemoryEntries: 1,
      detail: `Dungeon "${summary.name}" imported as a location memory entry.`,
    };
  }
}
