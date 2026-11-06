import type { PetSummary } from '../../shared/api-types.js';
import { DrabbitSvg } from './DrabbitSvg.js';
import { hasAiArt, type PetAnimState } from './visual-state.js';
import eatingPng from './assets/pip-eating.png';
import happyPng from './assets/pip-happy.png';
import idlePng from './assets/pip-idle.png';
import sickPng from './assets/pip-sick.png';
import sleepingPng from './assets/pip-sleeping.png';

/**
 * The pet's picture. Royal pets with a painterly portrait set render
 * as generated art (see visual-state.ts `hasAiArt`); everything else
 * falls back to the hand-drawn SVG, which remains the renderer for
 * all other furs and for the states the portrait set doesn't cover.
 * Motion for the portraits is whole-picture (the shared pet-*
 * keyframes), since a painting has no wing/ear layers to move.
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
    <img
      className={`pet-art pet-art-${anim}`}
      src={src}
      alt=""
      draggable={false}
    />
  );
}
