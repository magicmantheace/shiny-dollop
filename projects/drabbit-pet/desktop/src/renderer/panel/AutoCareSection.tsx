import { useCallback, useEffect, useState } from 'react';
import type { AutoCareState } from '../../shared/api-types.js';

/**
 * The Auto-care section of the care panel (owner-requested
 * 2026-11-05): one switch. While it's on, the app itself feeds,
 * cleans, plays with, and medicates the drabbit when the needs
 * call for it — through the same actions this panel uses, so the
 * care shows up in the event log like any other care.
 */
export function AutoCareSection() {
  const [state, setState] = useState<AutoCareState | null>(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setState(await window.drabbit.getAutoCareState());
    } catch {
      // Panel still works without the section.
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const apply = useCallback(async (enabled: boolean) => {
    setBusy(true);
    setNote(null);
    try {
      setState(await window.drabbit.setAutoCareEnabled(enabled));
    } catch (err) {
      setNote(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }, []);

  if (!state) {
    return (
      <section className="autocare">
        <h2>🛟 Auto care</h2>
        <p className="hint">Loading…</p>
      </section>
    );
  }

  return (
    <section className="autocare">
      <h2>🛟 Auto care</h2>
      <label className="autocare-toggle">
        <input
          type="checkbox"
          checked={state.enabled}
          disabled={busy}
          onChange={(e) => void apply(e.target.checked)}
        />
        Look after the drabbit automatically
      </label>
      <p className="hint">
        While on, the app feeds, cleans, plays, and gives medicine when needed —
        handy while testing. Sleep is never forced; the drabbit naps on its own.
      </p>
      {note && <p className="hint">{note}</p>}
    </section>
  );
}
