import { useEffect, useState } from 'react';
import type { CalculationRecord, CalculationResult } from '../../shared/types.js';
import { unwrap } from '../vcc.d.js';

interface Props {
  notify: (text: string) => void;
}

export default function HistoryView({ notify }: Props) {
  const [records, setRecords] = useState<CalculationRecord[]>([]);
  const [error, setError] = useState('');
  const [openId, setOpenId] = useState<number | null>(null);

  useEffect(() => {
    unwrap(window.vcc.history.list())
      .then(setRecords)
      .catch((e: Error) => setError(e.message));
  }, []);

  async function onExportCsv(id: number) {
    try {
      const data = await unwrap(window.vcc.export_.csv(id));
      if (!data.canceled) notify(`CSV saved to ${data.filePath}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <div className="card">
      <h2>Calculation history</h2>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      <ul className="list">
        {records.map((r) => {
          const result = JSON.parse(r.resultJson) as CalculationResult;
          const open = openId === r.id;
          return (
            <li key={r.id} style={{ display: 'block' }}>
              <div className="row" style={{ justifyContent: 'space-between' }}>
                <div>
                  <strong>
                    {r.mixDesignId}
                  </strong>{' '}
                  — {r.volume} {r.volumeUnit} (+{r.wasteAllowancePct}% waste)
                  <div className="meta">
                    {r.profileName} · {new Date(r.createdAt).toLocaleString()} ·{' '}
                    {result.warnings.length} warning{result.warnings.length === 1 ? '' : 's'}
                  </div>
                </div>
                <div className="row">
                  <button className="ghost" onClick={() => setOpenId(open ? null : r.id)}>
                    {open ? 'Hide' : 'Details'}
                  </button>
                  <button className="ghost" onClick={() => onExportCsv(r.id)}>
                    Export CSV
                  </button>
                </div>
              </div>
              {open && (
                <table className="results" style={{ marginTop: 8 }}>
                  <thead>
                    <tr>
                      <th scope="col">Material</th>
                      <th scope="col">Required</th>
                      <th scope="col">Gate</th>
                      <th scope="col">Remaining</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.materials.map((m) => (
                      <tr key={m.materialId}>
                        <td>{m.materialId}</td>
                        <td>{m.requiredQty.toFixed(2)}</td>
                        <td>{Number.isFinite(m.gateSettingNeeded) ? m.gateSettingNeeded.toFixed(1) : 'n/a'}</td>
                        <td>{m.remainingStock === undefined ? '—' : m.remainingStock.toFixed(2)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </li>
          );
        })}
        {records.length === 0 && <li>No calculations recorded yet.</li>}
      </ul>
    </div>
  );
}
