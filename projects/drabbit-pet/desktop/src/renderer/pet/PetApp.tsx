import { useEffect, useRef, useState } from 'react';
import type { PetSummary } from '../../shared/api-types.js';
import { PetArt } from './PetArt.js';
import {
  bridgeTransientFor,
  resolveAnimState,
  transientFromEvents,
  type TransientAnim,
} from './visual-state.js';
import './pet.css';

const TRANSIENT_MS = 1600;
const BRIDGE_NOTE_MS = 6000;

export function PetApp() {
  const [summary, setSummary] = useState<PetSummary | null>(null);
  const [hopping, setHopping] = useState(false);
  const [transient, setTransient] = useState<TransientAnim | null>(null);
  const [bridgeNote, setBridgeNote] = useState<string | null>(null);
  const transientTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const bridgeTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    let live = true;
    void window.drabbit
      .getSummary()
      .then((s) => {
        if (live) setSummary(s);
      })
      .catch(() => undefined);

    const playTransient = (t: TransientAnim) => {
      setTransient(t);
      if (transientTimer.current) clearTimeout(transientTimer.current);
      transientTimer.current = setTimeout(() => setTransient(null), TRANSIENT_MS);
    };
    const offChanged = window.drabbit.onChanged((e) => {
      setSummary(e.summary);
      const t = transientFromEvents(e.events);
      if (t) playTransient(t);
    });
    const offRoam = window.drabbit.onRoamState((s) => setHopping(s.hopping));
    const offBridge = window.drabbit.onBridgeReaction((r) => {
      setBridgeNote(r.text);
      if (bridgeTimer.current) clearTimeout(bridgeTimer.current);
      bridgeTimer.current = setTimeout(() => setBridgeNote(null), BRIDGE_NOTE_MS);
      const t = bridgeTransientFor(r.kind);
      if (t) playTransient(t);
    });
    return () => {
      live = false;
      offChanged();
      offRoam();
      offBridge();
      if (transientTimer.current) clearTimeout(transientTimer.current);
      if (bridgeTimer.current) clearTimeout(bridgeTimer.current);
    };
  }, []);

  if (!summary) {
    return <div className="pet-loading">…</div>;
  }

  const anim = resolveAnimState(summary, hopping, transient);

  return (
    <div
      className="pet-root"
      title={`${summary.name} — click for the care panel`}
      onClick={() => {
        void window.drabbit.openPanel().catch(() => undefined);
      }}
    >
      <PetArt summary={summary} anim={anim} />
      {bridgeNote && (
        <div className="bridge-bubble" aria-live="polite">
          {bridgeNote}
        </div>
      )}
      {summary.asleep && summary.stage !== 'dead' && (
        <div className="zzz" aria-hidden="true">
          <span>Z</span>
          <span>z</span>
          <span>z</span>
        </div>
      )}
      {summary.messes > 0 && summary.stage !== 'egg' && summary.stage !== 'dead' && (
        <div className="mess-badge" title={`${summary.messes} mess(es) to clean`}>
          💩 × {summary.messes}
        </div>
      )}
    </div>
  );
}
