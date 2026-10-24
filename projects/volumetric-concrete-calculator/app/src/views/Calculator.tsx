import { useEffect, useState } from 'react';
import type { CalculationResult, ProfileSummary } from '../../shared/types.js';
import { unwrap } from '../vcc.d.js';

interface Props {
  notify: (text: string) => void;
}

function num(v: string): number | undefined {
  if (v.trim() === '') return undefined;
  const n = Number(v);
  return Number.isFinite(n) ? n : undefined;
}

export default function CalculatorView({ notify }: Props) {
  const [profiles, setProfiles] = useState<ProfileSummary[]>([]);
  const [profileId, setProfileId] = useState('');
  const [mixId, setMixId] = useState('');
  const [mixes, setMixes] = useState<string[]>([]);
  const [volume, setVolume] = useState('8');
  const [volumeUnit, setVolumeUnit] = useState('m3');
  const [waste, setWaste] = useState('5');
  const [stockJson, setStockJson] = useState('');
  const [maxVolume, setMaxVolume] = useState('');
  const [maxPayload, setMaxPayload] = useState('');
  const [measured, setMeasured] = useState('');
  const [result, setResult] = useState<CalculationResult | null>(null);
  const [massUnit, setMassUnit] = useState('kg');
  const [calcId, setCalcId] = useState<number | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    unwrap(window.vcc.profiles.list())
      .then(setProfiles)
      .catch((e: Error) => setError(e.message));
  }, []);

  useEffect(() => {
    if (!profileId) {
      setMixes([]);
      return;
    }
    unwrap(window.vcc.profiles.get(Number(profileId)))
      .then((p) => {
        setMixes(p.mixes.map((m) => m.mixDesignId));
        setMixId((cur) => (p.mixes.some((m) => m.mixDesignId === cur) ? cur : (p.mixes[0]?.mixDesignId ?? '')));
      })
      .catch((e: Error) => setError(e.message));
  }, [profileId]);

  async function onCalculate() {
    setError('');
    setResult(null);
    const v = num(volume);
    const w = num(waste);
    if (v === undefined || v <= 0) {
      setError('Enter a target volume greater than 0.');
      return;
    }
    if (w === undefined || w < 0 || w > 100) {
      setError('Waste allowance must be between 0 and 100%.');
      return;
    }
    let startingStock: Record<string, number> | undefined;
    if (stockJson.trim()) {
      try {
        const parsed = JSON.parse(stockJson) as unknown;
        if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) throw new Error('bad shape');
        startingStock = parsed as Record<string, number>;
      } catch {
        setError('Starting stock must be JSON like {"cement": 10000, "sand": 30000}.');
        return;
      }
    }
    setBusy(true);
    try {
      const data = await unwrap(
        window.vcc.calc.run({
          profileId: Number(profileId),
          mixDesignId: mixId,
          volume: v,
          volumeUnit,
          wasteAllowancePct: w,
          ...(startingStock ? { startingStock } : {}),
          truckLimits: {
            ...(num(maxVolume) !== undefined ? { maxVolume: num(maxVolume) } : {}),
            ...(num(maxPayload) !== undefined ? { maxPayloadMass: num(maxPayload) } : {}),
          },
          ...(num(measured) !== undefined ? { measuredVolumeProducedM3: num(measured) } : {}),
        }),
      );
      setResult(data.result);
      setMassUnit(data.massUnit);
      setCalcId(data.id);
      notify('Calculation complete.');
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function onExportCsv() {
    if (calcId === null) return;
    try {
      const data = await unwrap(window.vcc.export_.csv(calcId));
      if (!data.canceled) notify(`CSV saved to ${data.filePath}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <div>
      <div className="card">
        <h2>Calculate batch quantities</h2>
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        <div className="grid2">
          <label className="field">
            Calibration profile
            <select value={profileId} onChange={(e) => setProfileId(e.target.value)}>
              <option value="">— select —</option>
              {profiles.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.profileName} ({p.materialCount} materials, {p.mixCount} mixes)
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            Mix design (nominal ID only)
            <select value={mixId} onChange={(e) => setMixId(e.target.value)} disabled={!profileId}>
              {mixes.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            Target volume
            <input value={volume} onChange={(e) => setVolume(e.target.value)} inputMode="decimal" />
          </label>
          <label className="field">
            Volume unit
            <select value={volumeUnit} onChange={(e) => setVolumeUnit(e.target.value)}>
              <option value="m3">m³</option>
              <option value="L">L</option>
              <option value="yd3">yd³</option>
            </select>
          </label>
          <label className="field">
            Waste allowance (%)
            <input value={waste} onChange={(e) => setWaste(e.target.value)} inputMode="decimal" />
          </label>
          <label className="field">
            Measured volume produced, m³ (optional — for yield comparison)
            <input value={measured} onChange={(e) => setMeasured(e.target.value)} inputMode="decimal" placeholder="e.g. 7.8" />
          </label>
        </div>
        <details className="advanced">
          <summary>Stock &amp; truck limits (optional)</summary>
          <div className="grid2" style={{ marginTop: 12 }}>
            <label className="field">
              Starting stock (JSON, profile units)
              <textarea
                rows={3}
                value={stockJson}
                onChange={(e) => setStockJson(e.target.value)}
                placeholder='{"cement": 10000, "sand": 30000}'
              />
            </label>
            <div className="grid2">
              <label className="field">
                Truck max volume (profile volume unit)
                <input value={maxVolume} onChange={(e) => setMaxVolume(e.target.value)} inputMode="decimal" />
              </label>
              <label className="field">
                Truck max payload (profile mass unit)
                <input value={maxPayload} onChange={(e) => setMaxPayload(e.target.value)} inputMode="decimal" />
              </label>
            </div>
          </div>
          <p className="disclaimer">
            Truck limit comparisons are estimates against values you enter — never a legal payload determination or
            rated-capacity claim.
          </p>
        </details>
        <div className="row" style={{ marginTop: 16 }}>
          <button className="primary" onClick={onCalculate} disabled={busy || !profileId || !mixId}>
            {busy ? 'Calculating…' : 'Calculate'}
          </button>
          {result && calcId !== null && (
            <button className="ghost" onClick={onExportCsv}>
              Export CSV (unit-aware)
            </button>
          )}
        </div>
      </div>

      {result && (
        <div className="card">
          <h2>
            Results — {result.mixDesignId} <span className="est-tag">estimate</span>
          </h2>
          <dl className="kv">
            <dt>Target volume</dt>
            <dd>
              {result.volume} {result.volumeUnit} (+{result.wasteAllowancePct}% waste → {result.totalVolumeM3.toFixed(3)} m³)
            </dd>
            <dt>Total material mass</dt>
            <dd>{result.totalMassKg.toFixed(1)} kg (mass-basis materials)</dd>
          </dl>

          {result.warnings.length > 0 && (
            <div className="warnings" role="alert">
              <h3>Warnings</h3>
              <ul>
                {result.warnings.map((w, i) => (
                  <li key={i}>
                    {w.message}
                    {w.estimateOnly && <span className="est-tag">estimate</span>}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <table className="results">
            <thead>
              <tr>
                <th scope="col">Material</th>
                <th scope="col">Required</th>
                <th scope="col">Gate setting</th>
                <th scope="col">Remaining stock</th>
              </tr>
            </thead>
            <tbody>
              {result.materials.map((m) => (
                <tr key={m.materialId} className={m.shortfall ? 'shortfall' : undefined}>
                  <td>
                    {m.materialId} <span style={{ color: '#6b655a' }}>({m.kind}, {m.basis})</span>
                  </td>
                  <td>
                    {m.requiredQty.toFixed(2)} {m.basis === 'mass' ? massUnit : result.volumeUnit}
                    <br />
                    <span style={{ color: '#6b655a', fontSize: 11 }}>theoretical {m.theoreticalQty.toFixed(2)}</span>
                  </td>
                  <td>{Number.isFinite(m.gateSettingNeeded) ? m.gateSettingNeeded.toFixed(1) : 'no calibration'}</td>
                  <td>
                    {m.remainingStock === undefined
                      ? '—'
                      : `${m.remainingStock.toFixed(2)}${m.shortfall ? ' (SHORTFALL)' : ''}${m.lowStock ? ' (low)' : ''}`}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {result.yieldComparison && (
            <>
              <h3>Theoretical vs measured yield</h3>
              <dl className="kv">
                <dt>Theoretical</dt>
                <dd>{result.yieldComparison.theoreticalVolumeM3.toFixed(3)} m³</dd>
                <dt>Measured</dt>
                <dd>{result.yieldComparison.measuredVolumeM3.toFixed(3)} m³</dd>
                <dt>Variance</dt>
                <dd>{(result.yieldComparison.varianceFraction * 100).toFixed(2)}%</dd>
              </dl>
            </>
          )}

          <h3>Assumptions</h3>
          <ul style={{ fontSize: 13, color: '#6b655a' }}>
            {result.assumptions.map((a, i) => (
              <li key={i}>{a}</li>
            ))}
          </ul>
          <p className="disclaimer">
            All quantities are estimates. Mix design IDs are nominal identifiers only — never verified structural
            performance claims. This tool does not determine code compliance, legal payload, or tested mix adequacy.
          </p>
        </div>
      )}
    </div>
  );
}
