import { readFileSync } from 'node:fs';
import { homedir } from 'node:os';
import path from 'node:path';
import {
  bridgeReactionFor,
  parseBridgeDisplayState,
  type BridgeReaction,
} from '../shared/bridge-reaction.js';
import type { Scheduler } from './tick-service.js';

/**
 * Watches the Muse PC Bridge's published display state
 * (display-state.json, written by the bridge's avatar-display
 * supervisor) and turns state changes into pet reactions.
 *
 * Strictly one-way and read-only: this service opens no sockets,
 * writes nothing, and holds no bridge credentials — it reads one
 * JSON file. A missing or malformed file is a quiet no-op (the
 * bridge may simply be running its console form, which does not
 * publish the file). Reactions are presentation only; the pet sim
 * never sees them (project determinism invariant).
 */

export const BRIDGE_POLL_MS = 2000;

const systemScheduler: Scheduler = {
  set: (fn, ms) => setInterval(fn, ms),
  clear: (handle) => clearInterval(handle as ReturnType<typeof setInterval>),
};

function defaultReadFile(p: string): string | null {
  try {
    return readFileSync(p, 'utf8');
  } catch {
    return null;
  }
}

/**
 * Candidate locations for the bridge's display-state.json, in
 * priority order: an explicit override wins, then the owner's
 * shiny-dollop checkout on D: (where the bridge lives on his PC),
 * then a home-relative checkout.
 */
export function bridgeStateCandidates(
  env: NodeJS.ProcessEnv = process.env,
  home: string = homedir(),
): string[] {
  const rel = path.join(
    'projects', 'muse-pc-bridge', 'agent', 'state', 'display-state.json',
  );
  const out: string[] = [];
  const override = env.DRABBIT_BRIDGE_STATE_FILE;
  if (override && override.trim()) out.push(override);
  out.push(path.join('D:\\shiny-dollop', rel));
  out.push(path.join(home, 'shiny-dollop', rel));
  return out;
}

export interface BridgeLinkDeps {
  onReaction: (reaction: BridgeReaction) => void;
  petName: () => string;
  /** Test seams; production uses the defaults. */
  candidates?: string[];
  readFile?: (p: string) => string | null;
  now?: () => number;
  scheduler?: Scheduler;
  intervalMs?: number;
}

export class BridgeLinkService {
  private handle: unknown = null;
  private lastState: string | null = null;
  private seen = false;

  constructor(private readonly deps: BridgeLinkDeps) {}

  get running(): boolean {
    return this.handle !== null;
  }

  /** One poll: read the first candidate that parses, react on change. */
  pollOnce(): void {
    const read = this.deps.readFile ?? defaultReadFile;
    const candidates =
      this.deps.candidates ?? bridgeStateCandidates();
    for (const p of candidates) {
      const text = read(p);
      if (text === null) continue;
      const parsed = parseBridgeDisplayState(text);
      if (!parsed) continue;
      if (!this.seen || parsed.state !== this.lastState) {
        const reaction = bridgeReactionFor(
          this.seen ? this.lastState : null,
          parsed,
          this.deps.petName(),
          (this.deps.now ?? Date.now)(),
        );
        this.lastState = parsed.state;
        this.seen = true;
        if (reaction) this.deps.onReaction(reaction);
      }
      return;
    }
  }

  start(): void {
    if (this.handle !== null) return;
    const scheduler = this.deps.scheduler ?? systemScheduler;
    const ms = this.deps.intervalMs ?? BRIDGE_POLL_MS;
    this.pollOnce();
    this.handle = scheduler.set(() => this.pollOnce(), ms);
  }

  stop(): void {
    if (this.handle === null) return;
    const scheduler = this.deps.scheduler ?? systemScheduler;
    scheduler.clear(this.handle);
    this.handle = null;
  }
}
