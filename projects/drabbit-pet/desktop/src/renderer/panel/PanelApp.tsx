import { useCallback, useEffect, useRef, useState } from 'react';
import type { PetEvent } from 'drabbit-core';
import type { ActionKind, PetSummary } from '../../shared/api-types.js';
import { ADULT_FORM_LABELS, MOOD_DISPLAY, STAGE_LABELS, formatAge, formatClock } from '../format.js';
import './panel.css';

const FEED_SIZE = 30;

function eventKey(e: PetEvent): string {
  return `${e.t}|${e.kind}|${e.detail}`;
}

/** Whether the UI should offer an action (mirrors the core's rules). */
export function canPerform(kind: ActionKind, s: PetSummary): boolean {
  const hatched = s.stage !== 'egg' && s.stage !== 'dead';
  switch (kind) {
    case 'hatch':
      return s.stage === 'egg' && s.readyToHatch;
    case 'feed-meal':
    case 'feed-snack':
    case 'play':
      return hatched && !s.asleep;
    case 'clean':
      return hatched;
    case 'sleep':
      return hatched && !s.asleep;
    case 'wake':
      return hatched && s.asleep;
    case 'medicine':
      return hatched && s.sick;
    case 'new-egg':
      return s.stage === 'dead';
  }
}

function NeedBar({ icon, label, value }: { icon: string; label: string; value: number }) {
  const rounded = Math.round(value);
  const level = rounded >= 50 ? 'good' : rounded >= 25 ? 'low' : 'critical';
  return (
    <div className="need-row">
      <span className="need-label">
        {icon} {label}
      </span>
      <div className="need-track">
        <div className={`need-fill ${level}`} style={{ width: `${rounded}%` }} />
      </div>
      <span className="need-value">{rounded}</span>
    </div>
  );
}

export function PanelApp() {
  const [summary, setSummary] = useState<PetSummary | null>(null);
  const [events, setEvents] = useState<PetEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const seenEvents = useRef<Set<string>>(new Set());

  const mergeEvents = useCallback((incoming: readonly PetEvent[]) => {
    const fresh = incoming.filter((e) => !seenEvents.current.has(eventKey(e)));
    if (fresh.length === 0) return;
    for (const e of fresh) seenEvents.current.add(eventKey(e));
    setEvents((prev) => [...prev, ...fresh].slice(-FEED_SIZE));
  }, []);

  useEffect(() => {
    let live = true;
    void window.drabbit
      .getSummary()
      .then((s) => {
        if (live) setSummary(s);
      })
      .catch(() => undefined);
    void window.drabbit
      .getEvents()
      .then((evts) => {
        if (live) mergeEvents(evts);
      })
      .catch(() => undefined);
    const off = window.drabbit.onChanged((e) => {
      setSummary(e.summary);
      mergeEvents(e.events);
    });
    return () => {
      live = false;
      off();
    };
  }, [mergeEvents]);

  const doAction = useCallback(
    async (kind: ActionKind) => {
      setBusy(true);
      setError(null);
      try {
        const outcome = await window.drabbit.action(kind);
        setSummary(outcome.summary);
        mergeEvents(outcome.events);
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        setBusy(false);
      }
    },
    [mergeEvents],
  );

  if (!summary) {
    return <div className="panel-loading">Waking the drabbit…</div>;
  }

  const mood = MOOD_DISPLAY[summary.mood];
  const isEgg = summary.stage === 'egg';
  const isDead = summary.stage === 'dead';

  const buttons: ReadonlyArray<{ kind: ActionKind; label: string; hint?: string }> = [
    { kind: 'hatch', label: '🐣 Hatch' },
    { kind: 'feed-meal', label: '🍽️ Feed meal' },
    { kind: 'feed-snack', label: '🍪 Snack' },
    { kind: 'play', label: '🎾 Play' },
    { kind: 'clean', label: '🧹 Clean' },
    { kind: 'sleep', label: '🌙 Put to sleep' },
    { kind: 'wake', label: '⏰ Wake' },
    { kind: 'medicine', label: '💊 Medicine' },
    { kind: 'new-egg', label: '🥚 New egg' },
  ];

  return (
    <div className="panel">
      <header className="panel-head">
        <div>
          <h1>{summary.name}</h1>
          <div className="subtitle">
            {STAGE_LABELS[summary.stage]}
            {summary.adultForm ? ` — ${ADULT_FORM_LABELS[summary.adultForm]}` : ''} · Generation{' '}
            {summary.generation}
          </div>
          <div className="subtitle">
            {isEgg
              ? summary.readyToHatch
                ? 'The egg is wiggling — ready to hatch!'
                : 'Incubating…'
              : isDead
                ? `Died of ${summary.deathCause ?? 'failing health'}`
                : `Age ${formatAge(summary.ageMs)}`}
          </div>
        </div>
        <div className="mood" title={`Mood: ${mood.label}`}>
          <span className="mood-emoji">{mood.emoji}</span>
          <span className="mood-label">{mood.label}</span>
        </div>
      </header>

      {summary.sick && !isDead && <div className="banner sick-banner">🤒 {summary.name} is sick — medicine will cure it.</div>}
      {isDead && <div className="banner dead-banner">👻 {summary.name} has departed. Start a new egg when you're ready.</div>}
      {error && <div className="banner error-banner">{error}</div>}

      {!isEgg && !isDead && (
        <section className="needs">
          <NeedBar icon="🍖" label="Hunger" value={summary.needs.hunger} />
          <NeedBar icon="😄" label="Happiness" value={summary.needs.happiness} />
          <NeedBar icon="⚡" label="Energy" value={summary.needs.energy} />
          <NeedBar icon="✨" label="Cleanliness" value={summary.needs.cleanliness} />
          <NeedBar icon="❤️" label="Health" value={summary.health} />
          <NeedBar icon="⭐" label="Care score" value={summary.careScore} />
          <div className="mess-line">
            {summary.messes > 0 ? `💩 ${summary.messes} mess(es) waiting to be cleaned` : '🧼 No messes'}
            {summary.asleep ? ' · 💤 Asleep' : ''}
          </div>
        </section>
      )}

      <section className="actions">
        {buttons
          .filter((b) => canPerform(b.kind, summary) || b.kind === 'hatch' || b.kind === 'new-egg')
          .map((b) => (
            <button
              key={b.kind}
              disabled={busy || !canPerform(b.kind, summary)}
              onClick={() => void doAction(b.kind)}
            >
              {b.label}
            </button>
          ))}
        {isEgg && !summary.readyToHatch && <p className="hint">The egg needs its incubation time before it can hatch.</p>}
      </section>

      <section className="feed">
        <h2>Recent events</h2>
        {events.length === 0 ? (
          <p className="hint">Nothing yet — the story starts with an egg.</p>
        ) : (
          <ul>
            {[...events].reverse().map((e, i) => (
              <li key={`${eventKey(e)}-${i}`}>
                <span className="feed-time">{formatClock(e.t)}</span> {e.detail}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
