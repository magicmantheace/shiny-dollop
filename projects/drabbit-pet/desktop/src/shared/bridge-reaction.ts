/**
 * Muse PC Bridge link — shared, pure pieces.
 *
 * The bridge's avatar-display supervisor publishes its current state
 * to a small JSON file on the PC (display-state.json, written by the
 * bridge — never by this app). The drabbit only OBSERVES that file:
 * this module parses it defensively and decides what reaction, if
 * any, a state change deserves. One-way by design — the pet can
 * never instruct the bridge, and nothing here touches the pet sim:
 * reactions are host/renderer presentation only.
 */

export interface BridgeDisplayState {
  state: string;
  art: string;
  label: string;
  /** Unix seconds when the state began (bridge clock). */
  since: number;
  /** Unix seconds when the file was last written (bridge clock). */
  updatedAt: number;
}

/** Parse a display-state.json body; anything malformed → null. */
export function parseBridgeDisplayState(text: string): BridgeDisplayState | null {
  let raw: unknown;
  try {
    raw = JSON.parse(text);
  } catch {
    return null;
  }
  if (!raw || typeof raw !== 'object') return null;
  const r = raw as Record<string, unknown>;
  if (typeof r.state !== 'string' || r.state.length === 0) return null;
  const num = (v: unknown): number =>
    typeof v === 'number' && Number.isFinite(v) ? v : 0;
  return {
    state: r.state,
    art: typeof r.art === 'string' ? r.art : '',
    label: typeof r.label === 'string' ? r.label : '',
    since: num(r.since),
    updatedAt: num(r.updated_at),
  };
}

export type BridgeReactionKind =
  | 'working'
  | 'session'
  | 'celebrate'
  | 'alert'
  | 'idle';

export interface BridgeReaction {
  kind: BridgeReactionKind;
  /** The bridge state that caused this reaction. */
  bridgeState: string;
  /** Line shown in the pet window's bubble. */
  text: string;
  /** Host clock (ms) when the reaction was produced. */
  at: number;
}

const BUSY_STATES = new Set(['working', 'session', 'celebrate', 'alert']);

/**
 * The reaction owed when the bridge's display state becomes `next`,
 * given the previously observed state (`null` = first observation).
 * Quiet by default: repeat states, transitional 'connecting', and a
 * first observation of a calm state produce no reaction. A first
 * observation of 'alert' DOES react — that one is worth surfacing
 * even if it predates the pet's launch.
 */
export function bridgeReactionFor(
  prevState: string | null,
  next: BridgeDisplayState,
  petName: string,
  now: number,
): BridgeReaction | null {
  if (prevState === next.state) return null;
  const mk = (kind: BridgeReactionKind, text: string): BridgeReaction => ({
    kind,
    bridgeState: next.state,
    text,
    at: now,
  });
  switch (next.state) {
    case 'working':
      return mk('working', `${petName} is watching Muse work`);
    case 'session':
      return mk('session', `${petName} noticed Muse open a work session`);
    case 'celebrate':
      return mk('celebrate', `Muse's update worked — ${petName} approves!`);
    case 'alert':
      return mk('alert', '⚠ Muse needs attention on the PC');
    case 'idle':
      if (prevState !== null && BUSY_STATES.has(prevState)) {
        return mk(
          'idle',
          prevState === 'alert'
            ? 'All clear — Muse is idle again'
            : `${petName} relaxes — Muse is idle`,
        );
      }
      return null;
    default:
      return null;
  }
}
