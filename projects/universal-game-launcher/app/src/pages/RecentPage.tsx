import { useEffect, useState } from 'react';
import type { Session } from '../../shared/types';
import { ApiCallError, formatDateTime, formatDuration, getApi, unwrap } from '../api';
import EmptyState from '../components/EmptyState';

const STATE_LABEL: Record<Session['state'], string> = {
  running: 'Running',
  completed: 'Completed',
  interrupted: 'Interrupted',
};

export default function RecentPage() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [confirmClear, setConfirmClear] = useState(false);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      setSessions(await unwrap(getApi().sessions.list({ limit: 100 })));
    } catch (err) {
      setError(err instanceof ApiCallError ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function clear() {
    try {
      await unwrap(getApi().sessions.clear());
      setConfirmClear(false);
      await load();
    } catch (err) {
      setError(err instanceof ApiCallError ? err.message : String(err));
    }
  }

  return (
    <section aria-label="Recently played">
      <div className="page-head">
        <h1>Recently Played</h1>
        {sessions.length > 0 && !confirmClear && (
          <button className="btn" onClick={() => setConfirmClear(true)}>
            Clear history
          </button>
        )}
      </div>
      {confirmClear && (
        <div className="confirm-box" role="alert">
          <p>
            <strong>Clear all recorded play sessions?</strong>
          </p>
          <p>This only deletes the launcher's own history. It does not touch any game files.</p>
          <div className="modal-actions">
            <button className="btn danger" onClick={clear}>
              Yes, clear history
            </button>
            <button className="btn" onClick={() => setConfirmClear(false)}>
              Keep history
            </button>
          </div>
        </div>
      )}
      {loading ? (
        <p className="muted">Loading sessions…</p>
      ) : error ? (
        <p className="form-error">{error}</p>
      ) : sessions.length === 0 ? (
        <EmptyState
          title="No sessions yet"
          body="Play a game and its sessions will show up here with start time and duration."
        />
      ) : (
        <table className="sessions">
          <thead>
            <tr>
              <th>Game</th>
              <th>Started</th>
              <th>Duration</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {sessions.map((s) => (
              <tr key={s.id}>
                <td>{s.gameTitle}</td>
                <td>{formatDateTime(s.startedAt)}</td>
                <td>{s.state === 'running' ? 'In progress' : formatDuration(s.durationMs)}</td>
                <td>
                  <span className={`badge ${s.state === 'interrupted' ? 'warn' : ''}`}>
                    {STATE_LABEL[s.state]}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
