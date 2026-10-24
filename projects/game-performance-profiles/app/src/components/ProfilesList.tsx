import { useState } from 'react';
import type {
  Capability,
  JournalEntry,
  Profile,
} from '../../shared/gpp-types';
import { deleteProfile } from '../gpp';
import { isProfileApplied } from '../hooks';
import { changeSummary } from '../validation';
import { CapabilityBadge } from './CapabilityBadge';

interface Props {
  profiles: Profile[];
  capabilities: Capability[];
  journal: JournalEntry[];
  onNew: () => void;
  onEdit: (profile: Profile) => void;
  onPreview: (profile: Profile) => void;
  onRollback: (profile: Profile) => void;
  onChanged: () => void;
}

export function ProfilesList({
  profiles,
  capabilities,
  journal,
  onNew,
  onEdit,
  onPreview,
  onRollback,
  onChanged,
}: Props) {
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<Profile | null>(null);

  async function handleDelete(profile: Profile) {
    setDeletingId(profile.id);
    setDeleteError(null);
    try {
      await deleteProfile(profile.id);
      setConfirmDelete(null);
      onChanged();
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : String(err));
    } finally {
      setDeletingId(null);
    }
  }

  if (profiles.length === 0) {
    return (
      <div className="empty" role="status">
        <p>No performance profiles yet.</p>
        <p className="muted">
          Create your first profile — for example, one that turns on Game Mode
          and raises your game's process priority — then preview exactly what
          will change before anything touches the OS.
        </p>
        <button type="button" className="btn btn-primary" onClick={onNew}>
          New profile
        </button>
      </div>
    );
  }

  return (
    <div>
      <div className="toolbar">
        <button type="button" className="btn btn-primary" onClick={onNew}>
          New profile
        </button>
      </div>
      {deleteError && (
        <div className="alert alert-error" role="alert">
          {deleteError}
        </div>
      )}
      <ul className="cards">
        {profiles.map((profile) => {
          const applied = isProfileApplied(profile.id, journal);
          return (
            <li key={profile.id} className="card">
              <div className="card-head">
                <h3>{profile.name}</h3>
                {applied ? (
                  <span className="badge badge-ok" title="Journal holds live (not rolled back) changes for this profile">
                    applied
                  </span>
                ) : (
                  <span className="badge badge-idle" title="No live changes recorded for this profile">
                    not applied
                  </span>
                )}
              </div>
              <p className="muted">
                {profile.changes.length}{' '}
                {profile.changes.length === 1 ? 'change' : 'changes'}
              </p>
              <ul className="change-list">
                {profile.changes.map((change, i) => (
                  <li key={i} className="change-row">
                    <span>{changeSummary(change)}</span>
                    <CapabilityBadge kind={change.kind} capabilities={capabilities} />
                  </li>
                ))}
              </ul>
              <div className="card-actions">
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={() => onPreview(profile)}
                >
                  Preview &amp; activate
                </button>
                <button type="button" className="btn" onClick={() => onEdit(profile)}>
                  Edit
                </button>
                <button
                  type="button"
                  className="btn"
                  onClick={() => onRollback(profile)}
                  disabled={!applied}
                  title={applied ? 'Roll back live changes from this profile' : 'Nothing to roll back'}
                >
                  Roll back
                </button>
                <button
                  type="button"
                  className="btn btn-danger"
                  onClick={() => setConfirmDelete(profile)}
                >
                  Delete
                </button>
              </div>
            </li>
          );
        })}
      </ul>

      {confirmDelete && (
        <div className="modal-backdrop">
          <div
            className="modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="delete-title"
          >
            <h2 id="delete-title">Delete profile?</h2>
            <p>
              Delete <strong>{confirmDelete.name}</strong>? This removes the
              profile definition. It does not undo OS changes already applied —
              use Roll back for that.
            </p>
            <div className="modal-actions">
              <button
                type="button"
                className="btn"
                onClick={() => setConfirmDelete(null)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn btn-danger"
                disabled={deletingId === confirmDelete.id}
                onClick={() => void handleDelete(confirmDelete)}
              >
                {deletingId === confirmDelete.id ? 'Deleting…' : 'Delete profile'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
