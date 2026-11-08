import type { PetSummary } from '../../shared/api-types.js';
import { DrabbitSvg } from './DrabbitSvg.js';
import { PetArt3D } from './PetArt3D.js';
import { hasAiArt, type PetAnimState } from './visual-state.js';
import eatingPng from './assets/pip-eating.png';
import happyPng from './assets/pip-happy.png';
import idlePng from './assets/pip-idle.png';
import sickPng from './assets/pip-sick.png';
import sleepingPng from './assets/pip-sleeping.png';

/**
 * The pet's picture. Royal pets render as the rigged 3D model
 * (PetArt3D, bones posed procedurally per state) for the states the
 * portrait set covers; if the 3D path fails for any reason it falls
 * back to that state's painterly portrait. Everything else — all
 * other furs, and states with no portrait (cleaning, healing,
 * hatching, egg, dead) — uses the hand-drawn SVG.
 */
const ROYAL_ART: Partial<Record<PetAnimState, string>> = {
  idle: idlePng,
  hopping: idlePng,
  eating: eatingPng,
  playing: happyPng,
  sick: sickPng,
  sleeping: sleepingPng,
};

export function PetArt({
  summary,
  anim,
}: {
  summary: PetSummary;
  anim: PetAnimState;
}) {
  const src = hasAiArt(summary.fur, anim) ? ROYAL_ART[anim] : undefined;
  if (!src) {
    return <DrabbitSvg summary={summary} anim={anim} />;
  }
  return (
    <PetArt3D
      anim={anim}
      fallback={
        <img
          className={`pet-art pet-art-${anim}`}
          src={src}
          alt=""
          draggable={false}
        />
      }
    />
  );
}
