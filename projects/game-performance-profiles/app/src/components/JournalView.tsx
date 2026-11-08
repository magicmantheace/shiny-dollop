import type { JournalEntry } from '../../shared/gpp-types';
import { CHANGE_KIND_META } from '../validation';

interface Props {
  entries: JournalEntry[];
}

function kindLabel(kind: string): string {
  return CHANGE_KIND_META.find((m) => m.kind === kind)?.label ?? kind;
}

function formatTime(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString();
}

export function JournalView({ entries }: Props) {
  if (entries.length === 0) {
    return (
      <div className="empty" role="status">
        <p>No changes recorded yet.</p>
        <p className="muted">
          Every change this app applies is written here first, with the
          previous value, so it can be rolled back exactly.
        </p>
      </div>
    );
  }
  return (
    <table className="table">
      <thead>
        <tr>
          <th scope="col">Profile</th>
          <th scope="col">Change</th>
          <th scope="col">Target</th>
          <th scope="col">Before → After</th>
          <th scope="col">Applied at</th>
          <th scope="col">Rolled back at</th>
        </tr>
      </thead>
      <tbody>
        {entries.map((e) => (
          <tr key={e.id} className={e.rolledBackAt ? 'rolled-back' : 'live'}>
            <td>{e.profileName}</td>
            <td>{kindLabel(e.changeKind)}</td>
            <td>{e.target}</td>
            <td>
              <span className="from">{e.before}</span>
              {' → '}
              <span className="to">{e.after}</span>
            </td>
            <td>{formatTime(e.appliedAt)}</td>
            <td>
              {e.rolledBackAt ? (
                formatTime(e.rolledBackAt)
              ) : (
                <span className="badge badge-ok">live</span>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
