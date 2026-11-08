import type { AdultForm, Mood, Stage } from 'drabbit-core';

/** "12 min" / "3 h 5 min" / "1 d 2 h" — age since hatch. */
export function formatAge(ageMs: number): string {
  const totalMin = Math.max(0, Math.floor(ageMs / 60000));
  if (totalMin < 60) return `${totalMin} min`;
  const hours = Math.floor(totalMin / 60);
  const mins = totalMin % 60;
  if (hours < 24) return mins > 0 ? `${hours} h ${mins} min` : `${hours} h`;
  const days = Math.floor(hours / 24);
  return `${days} d ${hours % 24} h`;
}

export const STAGE_LABELS: Record<Stage, string> = {
  egg: 'Egg',
  baby: 'Baby',
  child: 'Child',
  teen: 'Teen',
  adult: 'Adult',
  dead: 'Departed',
};

export const ADULT_FORM_LABELS: Record<AdultForm, string> = {
  radiant: 'Radiant Drabbit',
  content: 'Content Drabbit',
  scruffy: 'Scruffy Drabbit',
};

export const MOOD_DISPLAY: Record<Mood, { emoji: string; label: string }> = {
  waiting: { emoji: '🥚', label: 'Waiting' },
  joyful: { emoji: '😆', label: 'Joyful' },
  content: { emoji: '😊', label: 'Content' },
  okay: { emoji: '😐', label: 'Okay' },
  unhappy: { emoji: '😟', label: 'Unhappy' },
  miserable: { emoji: '😖', label: 'Miserable' },
  frail: { emoji: '🥀', label: 'Frail' },
  sick: { emoji: '🤒', label: 'Sick' },
  asleep: { emoji: '😴', label: 'Asleep' },
  gone: { emoji: '👻', label: 'Gone' },
};

/** Short local clock time for the event feed. */
export function formatClock(t: number): string {
  return new Date(t).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}
