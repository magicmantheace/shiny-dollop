// The AIDM house ruleset — an original, minimal tabletop ruleset written
// for this app. It is NOT derived from any published rulebook: four
// attributes, 2d6 checks against a difficulty number, hit points, and
// initiative by 2d6 + Agility. The deterministic engine in this file and
// in dice.ts is the ONLY authority on rules outcomes; narration (see
// electron/main/narrator.ts) is flavor text and can never change a result
// produced here.

export const ATTRIBUTES = ['might', 'agility', 'wits', 'spirit'] as const;
export type Attribute = (typeof ATTRIBUTES)[number];

export const ATTRIBUTE_LABELS: Record<Attribute, string> = {
  might: 'Might',
  agility: 'Agility',
  wits: 'Wits',
  spirit: 'Spirit',
};

/** Attribute ratings run from -2 (poor) to +4 (heroic); 0 is average. */
export const ATTRIBUTE_MIN = -2;
export const ATTRIBUTE_MAX = 4;

export type Stats = Record<Attribute, number>;

export function defaultStats(): Stats {
  return { might: 0, agility: 0, wits: 0, spirit: 0 };
}

export const DIFFICULTIES = [
  { key: 'easy', label: 'Easy', target: 7 },
  { key: 'standard', label: 'Standard', target: 9 },
  { key: 'hard', label: 'Hard', target: 11 },
  { key: 'heroic', label: 'Heroic', target: 13 },
] as const;

export type DifficultyKey = (typeof DIFFICULTIES)[number]['key'];

export function difficultyTarget(key: DifficultyKey): number {
  const found = DIFFICULTIES.find((d) => d.key === key);
  if (!found) throw new Error(`Unknown difficulty: ${key}`);
  return found.target;
}

/** A check succeeds when 2d6 + attribute meets or beats the target. */
export function checkSucceeds(total: number, target: number): boolean {
  return total >= target;
}

export const RULESET = {
  id: 'aidm-house-rules',
  version: '1.0.0',
  name: 'AIDM House Rules',
  summary:
    'Four attributes (Might, Agility, Wits, Spirit) rated -2..+4. Checks roll 2d6 + attribute against a difficulty target (Easy 7, Standard 9, Hard 11, Heroic 13). Initiative is 2d6 + Agility. Hit points track harm; at 0 HP a character is down.',
} as const;
