// Zod schemas for every IPC method's argument tuple (mirrors AidmApi).
import { z } from 'zod';

const id = z.string().min(1).max(200);
const optSessionId = z.union([id, z.null()]).optional();

const statsPatch = z
  .object({
    might: z.number().int().min(-2).max(4).optional(),
    agility: z.number().int().min(-2).max(4).optional(),
    wits: z.number().int().min(-2).max(4).optional(),
    spirit: z.number().int().min(-2).max(4).optional(),
  })
  .strict();

export const campaignsListSchema = z.tuple([]);
export const campaignsCreateSchema = z.tuple([
  z
    .object({
      name: z.string().min(1).max(200),
      setting: z.string().max(100_000).optional(),
      seed: z.string().max(200).optional(),
    })
    .strict(),
]);
export const campaignsGetSchema = z.tuple([id]);
export const campaignsDeleteSchema = z.tuple([id]);

export const sessionsListSchema = z.tuple([id]);
export const sessionsCreateSchema = z.tuple([
  id,
  z.object({ title: z.string().min(1).max(200) }).strict(),
]);
export const sessionsUpdateNotesSchema = z.tuple([id, z.string().max(100_000)]);
export const sessionsEndSchema = z.tuple([id]);

const characterInput = z
  .object({
    kind: z.enum(['pc', 'npc']),
    name: z.string().min(1).max(200),
    archetype: z.string().max(200).optional(),
    stats: statsPatch.optional(),
    hpMax: z.number().int().min(1).max(10_000).optional(),
    hpCurrent: z.number().int().min(0).max(10_000).optional(),
    inventory: z.array(z.string().min(1).max(200)).max(200).optional(),
    notes: z.string().max(100_000).optional(),
  })
  .strict();

export const charactersListSchema = z.tuple([id]);
export const charactersCreateSchema = z.tuple([id, characterInput]);
export const charactersUpdateSchema = z.tuple([id, characterInput.partial().strict()]);
export const charactersDeleteSchema = z.tuple([id]);

export const diceRollSchema = z.tuple([
  id,
  z
    .object({
      notation: z.string().min(1).max(50),
      label: z.string().max(200).optional(),
      sessionId: optSessionId,
    })
    .strict(),
]);

export const checkRollSchema = z.tuple([
  id,
  z
    .object({
      characterId: id,
      attribute: z.enum(['might', 'agility', 'wits', 'spirit']),
      difficulty: z.enum(['easy', 'standard', 'hard', 'heroic']),
      sessionId: optSessionId,
    })
    .strict(),
]);

export const logListSchema = z.tuple([id, optSessionId]);
export const logAddNoteSchema = z.tuple([id, z.string().min(1).max(100_000), optSessionId]);

export const encountersStartSchema = z.tuple([
  id,
  z
    .object({
      name: z.string().min(1).max(200),
      characterIds: z.array(id).min(1).max(50),
      sessionId: optSessionId,
    })
    .strict(),
]);
export const encountersGetActiveSchema = z.tuple([id]);
export const encountersAdvanceTurnSchema = z.tuple([id]);
const hpChange = z
  .object({
    characterId: id,
    amount: z.number().int().min(1).max(10_000),
    note: z.string().max(500).optional(),
  })
  .strict();
export const encountersApplyDamageSchema = z.tuple([id, hpChange]);
export const encountersApplyHealSchema = z.tuple([id, hpChange]);
export const encountersEndSchema = z.tuple([id]);

const memoryInput = z
  .object({
    kind: z.enum(['npc', 'location', 'fact']),
    title: z.string().min(1).max(300),
    body: z.string().max(100_000).optional(),
    tags: z.array(z.string().min(1).max(100)).max(50).optional(),
  })
  .strict();

export const memoryListSchema = z.tuple([id]);
export const memoryCreateSchema = z.tuple([id, memoryInput]);
export const memoryUpdateSchema = z.tuple([id, memoryInput.partial().strict()]);
export const memoryDeleteSchema = z.tuple([id]);
export const memorySearchSchema = z.tuple([id, z.string().max(500)]);

export const narrateSchema = z.tuple([id]);
export const settingsGetSchema = z.tuple([]);
export const settingsUpdateSchema = z.tuple([
  z
    .object({
      narrator: z.enum(['mock', 'local']),
      endpoint: z.string().max(500),
      model: z.string().max(200),
    })
    .strict(),
]);

export const exportCampaignSchema = z.tuple([id]);
export const importCampaignSchema = z.tuple([z.string().min(1).max(2_000_000)]);
export const importWorldbuildingSchema = z.tuple([id, z.string().min(1).max(2_000_000)]);
export const importDungeonManifestSchema = z.tuple([id, z.string().min(1).max(2_000_000)]);
