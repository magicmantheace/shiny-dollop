import type { SaveEnvelope } from 'drabbit-core';
import type { PetSummary } from './api-types.js';

/** Project a save envelope down to the presentation summary. Pure. */
export function toSummary(envelope: SaveEnvelope): PetSummary {
  const p = envelope.pet;
  return {
    id: p.id,
    name: p.name,
    fur: p.fur,
    stage: p.stage,
    adultForm: p.adultForm,
    mood: p.mood,
    needs: { ...p.needs },
    health: p.health,
    careScore: p.careScore,
    ageMs: p.ageMs,
    asleep: p.asleep,
    sick: p.sick,
    messes: p.messes,
    readyToHatch: p.readyToHatch,
    generation: envelope.lineage.generation,
    deathCause: p.deathCause,
  };
}
