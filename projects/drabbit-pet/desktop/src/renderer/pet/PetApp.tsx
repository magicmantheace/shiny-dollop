import { useEffect, useRef, useState } from 'react';
import type { PetSummary } from '../../shared/api-types.js';
import { DrabbitSvg } from './DrabbitSvg.js';
import { resolveAnimState, transientFromEvents, type TransientAnim } from './visual-state.js';
import './pet.css';

const TRANSIENT_MS = 1600;

export function PetApp() {
  const [summary, setSummary] = useState<PetSummary | null>(null);
  const [hopping, setHopping] = useState(false);
  const [transient, setTransient] = useState<TransientAnim | null>(null);
  const transientTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    let live = true;
    void window.drabbit
      .getSummary()
      .then((s) => {
        if (live) setSummary(s);
      })
      .catch(() => undefined);

    const offChanged = window.drabbit.onChanged((e) => {
      setSummary(e.summary);
      const t = transientFromEvents(e.events);
      if (t) {
        setTransient(t);
        if (transientTimer.current) clearTimeout(transientTimer.current);
        transientTimer.current = setTimeout(() => setTransient(null), TRANSIENT_MS);
      }
    });
    const offRoam = window.drabbit.onRoamState((s) => setHopping(s.hopping));
    return () => {
      live = false;
      offChanged();
      offRoam();
      if (transientTimer.current) clearTimeout(transientTimer.current);
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
      <DrabbitSvg summary={summary} anim={anim} />
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
