import type { Mood, PetState } from "./types.js";

/**
 * Mood is derived from state, never stored as truth (PET_DESIGN §9).
 * The checks run in the documented priority order.
 */
export function deriveMood(state: PetState): Mood {
  if (state.stage === "dead") return "gone";
  if (state.stage === "egg") return "waiting";
  if (state.sick) return "sick";
  if (state.asleep) return "asleep";
  if (state.health < 25) return "frail";
  const n = state.needs;
  const lowest = Math.min(n.hunger, n.happiness, n.energy, n.cleanliness);
  if (lowest < 15) return "miserable";
  const mean = (n.hunger + n.happiness + n.energy + n.cleanliness) / 4;
  if (mean >= 78) return "joyful";
  if (mean >= 58) return "content";
  if (mean >= 38) return "okay";
  return "unhappy";
}
