import { useState } from 'react';
import type { Profile, RollbackResult, RestoreAllResult } from '../shared/gpp-types';
import { rollbackProfile, restoreAll } from './gpp';
import { useGppData } from './hooks';
import { ProfilesList } from './components/ProfilesList';
import { ProfileEditor } from './components/ProfileEditor';
import { PreviewModal } from './components/PreviewModal';
import { JournalView } from './components/JournalView';
import { SnapshotsView } from './components/SnapshotsView';
import './styles.css';

type Tab = 'profiles' | 'journal' | 'snapshots';

interface RollbackNotice {
  kind: 'rollback' | 'restore-all';
  result: RollbackResult | RestoreAllResult;
}

export function App() {
  const data = useGppData();
  const [tab, setTab] = useState<Tab>('profiles');
  const [editing, setEditing] = useState<Profile | null | 'new'>(null);
  const [previewing, setPreviewing] = useState<Profile | null>(null);
  const [rollbackTarget, setRollbackTarget] = useState<Profile | null>(null);
  const [confirmRestoreAll, setConfirmRestoreAll] = useState(false);
  const [working, setWorking] = useState(false);
  const [notice, setNotice] = useState<RollbackNotice | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  async function handleRollback(profile: Profile) {
    setWorking(true);
    setActionError(null);
    try {
      const result = await rollbackProfile(profile.id);
      setNotice({ kind: 'rollback', result });
      data.refresh();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : String(err));
    } finally {
      setWorking(false);
      setRollbackTarget(null);
    }
  }

  async function handleRestoreAll() {
    setWorking(true);
    setActionError(null);
    try {
      const result = await restoreAll();
      setNotice({ kind: 'restore-all', result });
      data.refresh();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : String(err));
    } finally {
      setWorking(false);
      setConfirmRestoreAll(false);
    }
  }

  return (
    <div className="app">
      <header className="app-header">
        <div>
          <h1>Game Performance Profiles</h1>
          <p className="muted">
            Reversible, consented per-game performance settings.
          </p>
        </div>
        <button
          type="button"
          className="btn btn-danger"
          onClick={() => setConfirmRestoreAll(true)}
          title="Roll back every live change recorded in the journal"
        >
          Restore all changes
        </button>
      </header>

      <nav className="tabs" aria-label="Sections">
        {(
          [
            ['profiles', 'Profiles'],
            ['journal', 'Journal'],
            ['snapshots', 'Snapshots'],
          ] as [Tab, string][]
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            className={`tab${tab === id ? ' tab-active' : ''}`}
            aria-current={tab === id ? 'page' : undefined}
            onClick={() => setTab(id)}
          >
            {label}
            {id === 'journal' && data.journal.length > 0 && (
              <span className="tab-count">{data.journal.length}</span>
            )}
          </button>
        ))}
      </nav>

      <main>
        {data.loading && <p role="status">Loading…</p>}
        {data.error && (
          <div className="alert alert-error" role="alert">
            <strong>Couldn’t load data:</strong> {data.error}
          </div>
        )}
        {actionError && (
          <div className="alert alert-error" role="alert">
            {actionError}
          </div>
        )}
        {notice && (
          <div
            className={`alert ${notice.result.ok ? 'alert-ok' : 'alert-error'}`}
            role="status"
          >
            <p>
              <strong>
                {notice.kind === 'restore-all' ? 'Restore all' : 'Roll back'}{' '}
                {notice.result.ok ? 'complete' : 'finished with errors'}:
              </strong>{' '}
              {notice.result.rolledBack.length}{' '}
              {notice.result.rolledBack.length === 1 ? 'change' : 'changes'}{' '}
              restored to their previous values.
            </p>
            {notice.result.rolledBack.length > 0 && (
              <p className="muted small">
                Journal entries: {notice.result.rolledBack.join(', ')}
              </p>
            )}
            {notice.result.errors.length > 0 && (
              <ul>
                {notice.result.errors.map((e, i) => (
                  <li key={i}>{e}</li>
                ))}
              </ul>
            )}
            <button
              type="button"
              className="btn btn-sm"
              onClick={() => setNotice(null)}
            >
              Dismiss
            </button>
          </div>
        )}

        {!data.loading && !data.error && tab === 'profiles' && (
          <ProfilesList
            profiles={data.profiles}
            capabilities={data.capabilities}
            journal={data.journal}
            onNew={() => setEditing('new')}
            onEdit={(p) => setEditing(p)}
            onPreview={(p) => setPreviewing(p)}
            onRollback={(p) => setRollbackTarget(p)}
            onChanged={data.refresh}
          />
        )}
        {!data.loading && !data.error && tab === 'journal' && (
          <JournalView entries={data.journal} />
        )}
        {!data.loading && !data.error && tab === 'snapshots' && (
          <SnapshotsView snapshots={data.snapshots} onChanged={data.refresh} />
        )}
      </main>

      {editing && (
        <div className="modal-backdrop">
          <div
            className="modal modal-wide"
            role="dialog"
            aria-modal="true"
            aria-labelledby="editor-title"
          >
            <h2 id="editor-title">
              {editing === 'new'
                ? 'New profile'
                : `Edit profile — ${editing.name}`}
            </h2>
            <ProfileEditor
              profile={editing === 'new' ? undefined : editing}
              onSaved={() => {
                setEditing(null);
                data.refresh();
              }}
              onCancel={() => setEditing(null)}
            />
          </div>
        </div>
      )}

      {previewing && (
        <PreviewModal
          profile={previewing}
          onClose={() => setPreviewing(null)}
          onChanged={data.refresh}
        />
      )}

      {rollbackTarget && (
        <div className="modal-backdrop">
          <div
            className="modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="rollback-title"
          >
            <h2 id="rollback-title">Roll back profile?</h2>
            <p>
              Roll back all live changes recorded for{' '}
              <strong>{rollbackTarget.name}</strong>? Each change will be
              restored to the value it had before it was applied.
            </p>
            <div className="modal-actions">
              <button
                type="button"
                className="btn"
                onClick={() => setRollbackTarget(null)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn btn-primary"
                disabled={working}
                onClick={() => void handleRollback(rollbackTarget)}
              >
                {working ? 'Rolling back…' : 'Roll back'}
              </button>
            </div>
          </div>
        </div>
      )}

      {confirmRestoreAll && (
        <div className="modal-backdrop">
          <div
            className="modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="restore-all-title"
          >
            <h2 id="restore-all-title">Restore all changes?</h2>
            <p>
              This rolls back <strong>every</strong> live change in the journal,
              across all profiles, restoring each to its previous value. The
              journal entries are kept as a record.
            </p>
            <div className="modal-actions">
              <button
                type="button"
                className="btn"
                onClick={() => setConfirmRestoreAll(false)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn btn-danger"
                disabled={working}
                onClick={() => void handleRestoreAll()}
              >
                {working ? 'Restoring…' : 'Restore all changes'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
