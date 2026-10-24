import { useCallback, useEffect, useState } from 'react';
import type { ApprovedScript } from '../../shared/types';
import { dabErrorMessage, getDab } from '../lib/dab';
import { ConfirmDialog, ErrorBanner, formatDateTime } from './ui';

export function ScriptsManager() {
  const [scripts, setScripts] = useState<ApprovedScript[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [regName, setRegName] = useState('');
  const [regPath, setRegPath] = useState('');
  const [registering, setRegistering] = useState(false);
  const [unregisterTarget, setUnregisterTarget] =
    useState<ApprovedScript | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      setScripts(await getDab().scriptsList());
    } catch (e) {
      setError(dabErrorMessage(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function handleRegister() {
    if (!regName.trim() || !regPath.trim()) {
      setError('Give the script a name and a file path to register it.');
      return;
    }
    setRegistering(true);
    setError('');
    try {
      await getDab().scriptsRegister(regName.trim(), regPath.trim());
      setRegName('');
      setRegPath('');
      await refresh();
    } catch (e) {
      setError(dabErrorMessage(e));
    } finally {
      setRegistering(false);
    }
  }

  async function handleUnregister() {
    if (!unregisterTarget) return;
    setError('');
    try {
      await getDab().scriptsUnregister(unregisterTarget.id);
      setUnregisterTarget(null);
      await refresh();
    } catch (e) {
      setError(dabErrorMessage(e));
    }
  }

  return (
    <section aria-labelledby="scripts-heading">
      <div className="section-head">
        <h2 id="scripts-heading">Approved scripts</h2>
      </div>
      <p className="muted">
        Only scripts you explicitly register can run. A workflow step can only
        reference scripts from this list.
      </p>

      <ErrorBanner message={error} onDismiss={() => setError('')} />

      <form
        className="panel"
        onSubmit={(e) => {
          e.preventDefault();
          void handleRegister();
        }}
      >
        <h3>Register a script</h3>
        <label>
          Name
          <input
            type="text"
            value={regName}
            onChange={(e) => setRegName(e.target.value)}
            placeholder="e.g. Nightly cleanup"
          />
        </label>
        <label>
          File path
          <input
            type="text"
            value={regPath}
            onChange={(e) => setRegPath(e.target.value)}
            placeholder="Full path to the script file"
          />
        </label>
        <div className="form-actions">
          <button type="submit" className="primary" disabled={registering}>
            {registering ? 'Registering…' : 'Register script'}
          </button>
        </div>
      </form>

      <h3>Registered scripts ({scripts.length})</h3>
      {loading ? (
        <p>Loading scripts…</p>
      ) : scripts.length === 0 ? (
        <p className="muted">No scripts registered yet.</p>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th scope="col">Name</th>
              <th scope="col">Path</th>
              <th scope="col">Approved</th>
              <th scope="col">Actions</th>
            </tr>
          </thead>
          <tbody>
            {scripts.map((s) => (
              <tr key={s.id}>
                <td>{s.name}</td>
                <td className="mono">{s.path}</td>
                <td>{formatDateTime(s.approvedAt)}</td>
                <td>
                  <button
                    type="button"
                    className="danger-text"
                    onClick={() => setUnregisterTarget(s)}
                  >
                    Unregister
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {unregisterTarget && (
        <ConfirmDialog
          title={`Unregister script "${unregisterTarget.name}"?`}
          body={
            <p>
              Workflows that reference this script will no longer be able to
              run its steps until it is registered again.
            </p>
          }
          confirmLabel="Unregister script"
          danger
          onConfirm={() => void handleUnregister()}
          onCancel={() => setUnregisterTarget(null)}
        />
      )}
    </section>
  );
}
