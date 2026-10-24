// Deterministic PRNG utilities. The dice engine NEVER uses Math.random(),
// Date, or any other ambient entropy: a campaign's dice stream is a pure
// function of its seed and the number of draws consumed, so any recorded
// roll can be replayed and audited.

/** FNV-1a 32-bit string hash. */
export function hashSeed(seed: string): number {
  let h = 0x811c9dc5;
  for (let i = 0; i < seed.length; i++) {
    h ^= seed.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  return h >>> 0;
}

/**
 * One mulberry32 step as a pure function: given the current 32-bit state,
 * returns the drawn value in [0, 1) and the next state. Persisting the
 * state integer is enough to reproduce the entire stream.
 */
export function prngStep(state: number): { value: number; state: number } {
  const a = (state + 0x6d2b79f5) >>> 0;
  let t = a;
  t = Math.imul(t ^ (t >>> 15), t | 1);
  t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
  const value = ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  return { value, state: a };
}

/** A stateful stream built from repeated pure steps (tests, fixtures). */
export function streamFromState(initialState: number): {
  next: () => number;
  state: () => number;
} {
  let state = initialState >>> 0;
  return {
    next: () => {
      const step = prngStep(state);
      state = step.state;
      return step.value;
    },
    state: () => state,
  };
}

export function streamFromSeed(seed: string): {
  next: () => number;
  state: () => number;
} {
  return streamFromState(hashSeed(seed));
}
