// Deterministic per-step randomness.
//
// A roll is a pure function of (pet id, absolute step index, salt), so the
// same pet advanced through the same steps always gets the same rolls —
// no matter how the host chunks its advance() calls. FNV-1a hash with a
// MurmurHash-style finalizer for decent bit dispersion.

export function stepRoll(petId: string, stepIndex: number, salt: number): number {
  const key = `${petId}:${stepIndex}:${salt}`;
  let h = 2166136261 >>> 0; // FNV offset basis
  for (let i = 0; i < key.length; i++) {
    h ^= key.charCodeAt(i);
    h = Math.imul(h, 16777619); // FNV prime
  }
  h ^= h >>> 13;
  h = Math.imul(h, 0x5bd1e995);
  h ^= h >>> 15;
  return (h >>> 0) / 4294967296; // [0, 1)
}

/** Roll salts, so different systems never share a roll within a step. */
export const ROLL_MESS = 1;
export const ROLL_SICK = 2;
