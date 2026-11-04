// Deterministic PRNG utilities. The generator NEVER uses Math.random(),
// Date, or any other ambient entropy: the same seed always produces the
// same stream, on every platform and every process run.

/** FNV-1a 32-bit string hash. */
export function hashSeed(seed: string): number {
  let h = 0x811c9dc5;
  for (let i = 0; i < seed.length; i++) {
    h ^= seed.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  return h >>> 0;
}

/** mulberry32 PRNG: tiny, fast, and fully deterministic. */
export function mulberry32(initialState: number): () => number {
  let a = initialState >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export type Rng = () => number;

export function rngFromSeed(seed: string): Rng {
  return mulberry32(hashSeed(seed));
}

/** Integer in [min, max] inclusive, drawn from the stream. */
export function nextInt(rng: Rng, min: number, max: number): number {
  return min + Math.floor(rng() * (max - min + 1));
}

/** Pick one element; the array must be non-empty. */
export function pick<T>(rng: Rng, items: readonly T[]): T {
  return items[Math.floor(rng() * items.length)] as T;
}
