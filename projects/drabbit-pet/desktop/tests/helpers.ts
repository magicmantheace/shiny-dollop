import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import type { Clock } from '../src/main/pet-service.js';

/** A clock the test moves by hand — the sim never sees a real time. */
export class FakeClock implements Clock {
  constructor(private t: number) {}
  now(): number {
    return this.t;
  }
  set(t: number): void {
    this.t = t;
  }
  advanceMs(ms: number): void {
    this.t += ms;
  }
}

export function tmpDir(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'drabbit-test-'));
}

/** Deterministic rand: yields `values` in order, then `fallback`. */
export function scriptedRand(values: number[], fallback = 0.5): () => number {
  let i = 0;
  return () => (i < values.length ? (values[i++] as number) : fallback);
}
