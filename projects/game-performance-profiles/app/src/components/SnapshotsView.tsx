import { useState } from 'react';
import { SNAPSHOT_NOTE } from '../../shared/gpp-types';
import type { ResourceSnapshot } from '../../shared/gpp-types';
import { takeSnapshot } from '../gpp';

interface Props {
  snapshots: ResourceSnapshot[];
  onChanged: () => void;
}

function formatTime(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString();
}

export function SnapshotsView({ snapshots, onChanged }: Props) {
  const [label, setLabel] = useState('');
  const [taking, setTaking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [compareA, setCompareA] = useState('');
  const [compareB, setCompareB] = useState('');

  async function handleTake() {
    const trimmed = label.trim();
    if (!trimmed) {
      setError('Give the snapshot a label first, e.g. “before Elden Ring”.');
      return;
    }
    setTaking(true);
    setError(null);
    try {
      await takeSnapshot(trimmed);
      setLabel('');
      onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setTaking(false);
    }
  }

  const snapA = snapshots.find((s) => s.id === compareA);
  const snapB = snapshots.find((s) => s.id === compareB);

  return (
    <div>
      <div className="snapshot-form">
        <label htmlFor="snapshot-label">New snapshot label</label>
        <div className="snapshot-form-row">
          <input
            id="snapshot-label"
            type="text"
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            placeholder="e.g. before activating Elden Ring profile"
            maxLength={120}
          />
          <button
            type="button"
            className="btn btn-primary"
            disabled={taking}
            onClick={() => void handleTake()}
          >
            {taking ? 'Taking…' : 'Take snapshot'}
          </button>
        </div>
        {error && (
          <div className="alert alert-error" role="alert">
            {error}
          </div>
        )}
      </div>

      {snapshots.length === 0 ? (
        <div className="empty" role="status">
          <p>No snapshots yet.</p>
          <p className="muted">
            Take one before activating a profile and one after, then compare
            them to see the rough difference.
          </p>
        </div>
      ) : (
        <>
          <ul className="cards">
            {snapshots.map((s) => (
              <li key={s.id} className="card">
                <div className="card-head">
                  <h3>{s.label}</h3>
                </div>
                <p className="muted">{formatTime(s.takenAt)}</p>
                <dl className="stats">
                  <div>
                    <dt>CPU</dt>
                    <dd>{s.cpuPercent.toFixed(1)}%</dd>
                  </div>
                  <div>
                    <dt>Memory</dt>
                    <dd>{s.memoryMb.toFixed(0)} MB</dd>
                  </div>
                </dl>
                <p className="snapshot-note">{s.note || SNAPSHOT_NOTE}</p>
              </li>
            ))}
          </ul>

          {snapshots.length >= 2 && (
            <div className="compare">
              <h3>Compare two snapshots</h3>
              <div className="compare-row">
                <label>
                  Before
                  <select
                    value={compareA}
                    onChange={(e) => setCompareA(e.target.value)}
                  >
                    <option value="">Pick a snapshot…</option>
                    {snapshots.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  After
                  <select
                    value={compareB}
                    onChange={(e) => setCompareB(e.target.value)}
                  >
                    <option value="">Pick a snapshot…</option>
                    {snapshots.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.label}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              {snapA && snapB && (
                <table className="table">
                  <thead>
                    <tr>
                      <th scope="col">Metric</th>
                      <th scope="col">Before ({snapA.label})</th>
                      <th scope="col">After ({snapB.label})</th>
                      <th scope="col">Δ</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td>CPU %</td>
                      <td>{snapA.cpuPercent.toFixed(1)}%</td>
                      <td>{snapB.cpuPercent.toFixed(1)}%</td>
                      <td>
                        {(snapB.cpuPercent - snapA.cpuPercent).toFixed(1)} pp
                      </td>
                    </tr>
                    <tr>
                      <td>Memory</td>
                      <td>{snapA.memoryMb.toFixed(0)} MB</td>
                      <td>{snapB.memoryMb.toFixed(0)} MB</td>
                      <td>{(snapB.memoryMb - snapA.memoryMb).toFixed(0)} MB</td>
                    </tr>
                  </tbody>
                </table>
              )}
              <p className="snapshot-note">{SNAPSHOT_NOTE}</p>
            </div>
          )}
        </>
      )}
    </div>
  );
}
