import { useEffect, useState } from 'react';
import type { CalibrationProfile, ProfileSummary } from '../../shared/types.js';
import { unwrap } from '../vcc.d.js';

interface Props {
  notify: (text: string) => void;
}

const KINDS = ['cement', 'sand', 'gravel', 'water', 'admixture', 'other'] as const;

const blankProfile = (): CalibrationProfile => ({
  profileName: '',
  units: { volume: 'm3', mass: 'kg' },
  materials: [{ materialId: 'cement', kind: 'cement', description: '' }],
  calibrations: [{ materialId: 'cement', gateSetting: 40, measuredOutputPerUnit: 8, measuredAt: '', source: '' }],
  mixes: [
    {
      mixDesignId: 'NOM-25',
      note: '',
      nominalOnly: true,
      components: [{ materialId: 'cement', targetPerM3: 320 }],
    },
  ],
});

function clean(profile: CalibrationProfile): CalibrationProfile {
  return {
    profileName: profile.profileName.trim(),
    units: profile.units,
    materials: profile.materials
      .filter((m) => m.materialId.trim())
      .map((m) => ({
        materialId: m.materialId.trim(),
        kind: m.kind,
        ...(m.description?.trim() ? { description: m.description.trim() } : {}),
      })),
    calibrations: profile.calibrations
      .filter((c) => c.materialId.trim())
      .map((c) => ({
        materialId: c.materialId.trim(),
        gateSetting: c.gateSetting,
        measuredOutputPerUnit: c.measuredOutputPerUnit,
        ...(c.measuredAt?.trim() ? { measuredAt: c.measuredAt.trim() } : {}),
        ...(c.source?.trim() ? { source: c.source.trim() } : {}),
      })),
    mixes: profile.mixes
      .filter((m) => m.mixDesignId.trim())
      .map((m) => ({
        mixDesignId: m.mixDesignId.trim(),
        ...(m.note?.trim() ? { note: m.note.trim() } : {}),
        nominalOnly: true as const,
        components: m.components
          .filter((c) => c.materialId.trim())
          .map((c) => ({ materialId: c.materialId.trim(), targetPerM3: c.targetPerM3 })),
      })),
  };
}

export default function ProfilesView({ notify }: Props) {
  const [profiles, setProfiles] = useState<ProfileSummary[]>([]);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [draft, setDraft] = useState<CalibrationProfile>(blankProfile);
  const [error, setError] = useState('');

  const refresh = () =>
    unwrap(window.vcc.profiles.list())
      .then(setProfiles)
      .catch((e: Error) => setError(e.message));

  useEffect(() => {
    refresh();
  }, []);

  function startNew() {
    setEditingId(null);
    setDraft(blankProfile());
    setError('');
  }

  async function startEdit(id: number) {
    try {
      const p = await unwrap(window.vcc.profiles.get(id));
      setEditingId(id);
      setDraft({
        profileName: p.profileName,
        units: p.units,
        materials: p.materials.map((m) => ({ ...m, description: m.description ?? '' })),
        calibrations: p.calibrations.map((c) => ({ ...c, measuredAt: c.measuredAt ?? '', source: c.source ?? '' })),
        mixes: p.mixes.map((m) => ({ ...m, note: m.note ?? '' })),
      });
      setError('');
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function onSave() {
    setError('');
    try {
      const cleaned = clean(draft);
      if (editingId === null) {
        const { id } = await unwrap(window.vcc.profiles.create(cleaned));
        notify(`Profile saved (id ${id}).`);
      } else {
        await unwrap(window.vcc.profiles.update(editingId, cleaned));
        notify('Profile updated.');
      }
      setEditingId(null);
      setDraft(blankProfile());
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function onDelete(id: number) {
    if (!window.confirm('Delete this calibration profile? This cannot be undone.')) return;
    try {
      await unwrap(window.vcc.profiles.remove(id));
      notify('Profile deleted.');
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function onExport(id: number) {
    try {
      const data = await unwrap(window.vcc.export_.envelope(id));
      if (!data.canceled) notify(`Calibration envelope (v1.0.0) saved to ${data.filePath}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function onImport() {
    try {
      const data = await unwrap(window.vcc.import_.envelope());
      if (!data.canceled) {
        notify(`Imported "${data.profileName}" as profile ${data.id}.`);
        await refresh();
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  const set = (patch: Partial<CalibrationProfile>) => setDraft((d) => ({ ...d, ...patch }));

  return (
    <div>
      <div className="card">
        <h2>Calibration profiles</h2>
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        <div className="row" style={{ marginBottom: 12 }}>
          <button className="primary" onClick={startNew}>
            New profile
          </button>
          <button className="ghost" onClick={onImport}>
            Import v1.0.0 envelope…
          </button>
        </div>
        <ul className="list">
          {profiles.map((p) => (
            <li key={p.id}>
              <div>
                <strong>{p.profileName}</strong>
                <div className="meta">
                  {p.materialCount} materials · {p.mixCount} mixes · units {p.volumeUnit}/{p.massUnit}
                </div>
              </div>
              <div className="row">
                <button className="ghost" onClick={() => onExport(p.id)}>
                  Export envelope
                </button>
                <button className="ghost" onClick={() => startEdit(p.id)}>
                  Edit
                </button>
                <button className="danger" onClick={() => onDelete(p.id)}>
                  Delete
                </button>
              </div>
            </li>
          ))}
          {profiles.length === 0 && <li>No profiles yet — create one to begin.</li>}
        </ul>
      </div>

      <div className="card">
        <h2>{editingId === null ? 'New profile' : `Edit profile #${editingId}`}</h2>
        <div className="grid2">
          <label className="field">
            Profile name
            <input value={draft.profileName} onChange={(e) => set({ profileName: e.target.value })} />
          </label>
          <div className="grid2">
            <label className="field">
              Volume unit
              <select
                value={draft.units.volume}
                onChange={(e) => set({ units: { ...draft.units, volume: e.target.value as 'm3' | 'L' | 'yd3' } })}
              >
                <option value="m3">m³</option>
                <option value="L">L</option>
                <option value="yd3">yd³</option>
              </select>
            </label>
            <label className="field">
              Mass unit
              <select
                value={draft.units.mass}
                onChange={(e) => set({ units: { ...draft.units, mass: e.target.value as 'kg' | 't' | 'lb' } })}
              >
                <option value="kg">kg</option>
                <option value="t">t</option>
                <option value="lb">lb</option>
              </select>
            </label>
          </div>
        </div>

        <h3>Materials</h3>
        {draft.materials.map((m, i) => (
          <div className="grid3" key={i} style={{ marginBottom: 8 }}>
            <label className="field">
              Material ID
              <input
                value={m.materialId}
                onChange={(e) =>
                  set({ materials: draft.materials.map((x, j) => (j === i ? { ...x, materialId: e.target.value } : x)) })
                }
              />
            </label>
            <label className="field">
              Kind
              <select
                value={m.kind}
                onChange={(e) =>
                  set({
                    materials: draft.materials.map((x, j) =>
                      j === i ? { ...x, kind: e.target.value as (typeof KINDS)[number] } : x,
                    ),
                  })
                }
              >
                {KINDS.map((k) => (
                  <option key={k} value={k}>
                    {k}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              Description
              <input
                value={m.description ?? ''}
                onChange={(e) =>
                  set({ materials: draft.materials.map((x, j) => (j === i ? { ...x, description: e.target.value } : x)) })
                }
              />
            </label>
          </div>
        ))}
        <button
          className="ghost"
          onClick={() => set({ materials: [...draft.materials, { materialId: '', kind: 'other', description: '' }] })}
        >
          Add material
        </button>

        <h3>Gate calibrations</h3>
        <p style={{ fontSize: 12, color: '#6b655a' }}>
          Measured output per gate unit, in the profile's mass unit (cement/sand/gravel) or volume unit
          (water/admixture). Record the measurement source — it stays with the profile.
        </p>
        {draft.calibrations.map((c, i) => (
          <div className="grid3" key={i} style={{ marginBottom: 8 }}>
            <label className="field">
              Material ID
              <input
                value={c.materialId}
                onChange={(e) =>
                  set({
                    calibrations: draft.calibrations.map((x, j) => (j === i ? { ...x, materialId: e.target.value } : x)),
                  })
                }
              />
            </label>
            <label className="field">
              Gate setting
              <input
                type="number"
                min="0"
                step="any"
                value={Number.isFinite(c.gateSetting) ? c.gateSetting : ''}
                onChange={(e) =>
                  set({
                    calibrations: draft.calibrations.map((x, j) =>
                      j === i ? { ...x, gateSetting: Number(e.target.value) } : x,
                    ),
                  })
                }
              />
            </label>
            <label className="field">
              Measured output / gate unit
              <input
                type="number"
                min="0"
                step="any"
                value={Number.isFinite(c.measuredOutputPerUnit) ? c.measuredOutputPerUnit : ''}
                onChange={(e) =>
                  set({
                    calibrations: draft.calibrations.map((x, j) =>
                      j === i ? { ...x, measuredOutputPerUnit: Number(e.target.value) } : x,
                    ),
                  })
                }
              />
            </label>
            <label className="field">
              Measured at / source
              <input
                value={c.source ?? ''}
                onChange={(e) =>
                  set({
                    calibrations: draft.calibrations.map((x, j) => (j === i ? { ...x, source: e.target.value } : x)),
                  })
                }
                placeholder="e.g. scale ticket #1042"
              />
            </label>
          </div>
        ))}
        <button
          className="ghost"
          onClick={() =>
            set({
              calibrations: [
                ...draft.calibrations,
                { materialId: '', gateSetting: NaN, measuredOutputPerUnit: NaN, measuredAt: '', source: '' },
              ],
            })
          }
        >
          Add calibration
        </button>

        <h3>Mix designs (nominal IDs only)</h3>
        {draft.mixes.map((mix, i) => (
          <div className="card" key={i} style={{ background: '#faf8f3' }}>
            <div className="grid2">
              <label className="field">
                Mix design ID (nominal only — never a structural claim)
                <input
                  value={mix.mixDesignId}
                  onChange={(e) =>
                    set({ mixes: draft.mixes.map((x, j) => (j === i ? { ...x, mixDesignId: e.target.value } : x)) })
                  }
                />
              </label>
              <label className="field">
                Note
                <input
                  value={mix.note ?? ''}
                  onChange={(e) =>
                    set({ mixes: draft.mixes.map((x, j) => (j === i ? { ...x, note: e.target.value } : x)) })
                  }
                />
              </label>
            </div>
            {mix.components.map((comp, k) => (
              <div className="grid2" key={k} style={{ marginTop: 8 }}>
                <label className="field">
                  Material ID
                  <input
                    value={comp.materialId}
                    onChange={(e) =>
                      set({
                        mixes: draft.mixes.map((x, j) =>
                          j === i
                            ? {
                                ...x,
                                components: x.components.map((c, l) =>
                                  l === k ? { ...c, materialId: e.target.value } : c,
                                ),
                              }
                            : x,
                        ),
                      })
                    }
                  />
                </label>
                <label className="field">
                  Target per m³
                  <input
                    type="number"
                    min="0"
                    step="any"
                    value={Number.isFinite(comp.targetPerM3) ? comp.targetPerM3 : ''}
                    onChange={(e) =>
                      set({
                        mixes: draft.mixes.map((x, j) =>
                          j === i
                            ? {
                                ...x,
                                components: x.components.map((c, l) =>
                                  l === k ? { ...c, targetPerM3: Number(e.target.value) } : c,
                                ),
                              }
                            : x,
                        ),
                      })
                    }
                  />
                </label>
              </div>
            ))}
            <button
              className="ghost"
              style={{ marginTop: 8 }}
              onClick={() =>
                set({
                  mixes: draft.mixes.map((x, j) =>
                    j === i ? { ...x, components: [...x.components, { materialId: '', targetPerM3: NaN }] } : x,
                  ),
                })
              }
            >
              Add component
            </button>
          </div>
        ))}
        <button
          className="ghost"
          onClick={() =>
            set({
              mixes: [
                ...draft.mixes,
                { mixDesignId: '', note: '', nominalOnly: true, components: [{ materialId: '', targetPerM3: NaN }] },
              ],
            })
          }
        >
          Add mix design
        </button>

        <div className="row" style={{ marginTop: 16 }}>
          <button className="primary" onClick={onSave}>
            Save profile
          </button>
          <button className="ghost" onClick={startNew}>
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
