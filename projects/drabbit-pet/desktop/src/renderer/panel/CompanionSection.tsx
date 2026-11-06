import { useCallback, useEffect, useState } from 'react';
import type { CompanionState } from '../../shared/api-types.js';

/**
 * The Companion section of the care panel (P3): the companion
 * server's switch, address, pairing token, and live stats. The token
 * is masked by default — it's a secret (project AGENTS.md rule 8) —
 * with explicit Show and Copy affordances for pairing the phone.
 */

function maskToken(token: string): string {
  if (!token) return '';
  if (token.length <= 4) return '••••';
  return `${'•'.repeat(12)}${token.slice(-4)}`;
}

export function CompanionSection() {
  const [state, setState] = useState<CompanionState | null>(null);
  const [showToken, setShowToken] = useState(false);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setState(await window.drabbit.getCompanionState());
    } catch {
      // Panel still works without the section; a later refresh retries.
    }
  }, []);

  useEffect(() => {
    void refresh();
    // Stats move when the phone talks to the server; pet changes are
    // a cheap, already-flowing signal to re-read them on.
    const off = window.drabbit.onChanged(() => {
      void refresh();
    });
    return off;
  }, [refresh]);

  const apply = useCallback(async (fn: () => Promise<CompanionState>) => {
    setBusy(true);
    setNote(null);
    try {
      setState(await fn());
    } catch (err) {
      setNote(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }, []);

  const copyToken = useCallback(async () => {
    if (!state?.token) return;
    try {
      await navigator.clipboard.writeText(state.token);
      setNote('Token copied — paste it into the phone app when pairing.');
    } catch {
      setShowToken(true);
      setNote('Copy failed — the token is shown above so you can copy it by hand.');
    }
  }, [state?.token]);

  if (!state) {
    return (
      <section className="companion">
        <h2>📱 Companion server</h2>
        <p className="hint">Loading…</p>
      </section>
    );
  }

  const statusLine =
    state.status === 'on'
      ? `On — ${state.url ?? ''}`
      : state.status === 'error'
        ? `Error — ${state.error ?? 'failed to start'}`
        : 'Off';

  return (
    <section className="companion">
      <h2>📱 Companion server</h2>
      <div className="companion-status">
        <span className={`companion-dot ${state.status}`} aria-hidden="true" />
        <span>{statusLine}</span>
      </div>

      <label className="companion-toggle">
        <input
          type="checkbox"
          checked={state.enabled}
          disabled={busy}
          onChange={(e) => void apply(() => window.drabbit.setCompanionEnabled(e.target.checked))}
        />
        Let the phone app see and care for this drabbit
      </label>

      {state.token ? (
        <div className="companion-token">
          <div className="companion-token-row">
            <span className="companion-token-label">Pairing token</span>
            <code className="companion-token-value">
              {showToken ? state.token : maskToken(state.token)}
            </code>
          </div>
          <div className="companion-buttons">
            <button disabled={busy} onClick={() => setShowToken((v) => !v)}>
              {showToken ? 'Hide' : 'Show'}
            </button>
            <button disabled={busy} onClick={() => void copyToken()}>
              Copy
            </button>
            <button
              disabled={busy}
              onClick={() => void apply(() => window.drabbit.regenerateCompanionToken())}
            >
              Regenerate token
            </button>
          </div>
          <p className="hint">
            Regenerating disconnects the phone until it is paired with the new token.
          </p>
        </div>
      ) : (
        <p className="hint">The pairing token is created the first time you switch this on.</p>
      )}

      {state.stats && (
        <p className="hint">
          Requests: {state.stats.requestCount} · Auth failures: {state.stats.authFailures}
          {state.stats.lastClient ? ` · Last client: ${state.stats.lastClient}` : ''}
        </p>
      )}
      {note && <p className="hint">{note}</p>}
    </section>
  );
}
