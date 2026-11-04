import { useState } from 'react';
import type { ChangeKind, ChangeSpec, Profile } from '../../shared/gpp-types';
import { createProfile, updateProfile } from '../gpp';
import {
  CHANGE_KIND_META,
  PRIORITY_OPTIONS,
  defaultParams,
  validateChangeParams,
  validateProfileName,
} from '../validation';

interface DraftChange {
  localId: string;
  kind: ChangeKind;
  params: Record<string, string>;
}

interface Props {
  /** When set, the editor updates this profile instead of creating one. */
  profile?: Profile;
  onSaved: () => void;
  onCancel: () => void;
}

let localIdCounter = 0;
function nextLocalId(): string {
  localIdCounter += 1;
  return `draft-${localIdCounter}`;
}

function toDraft(spec: ChangeSpec): DraftChange {
  return { localId: nextLocalId(), kind: spec.kind, params: { ...spec.params } };
}

export function ProfileEditor({ profile, onSaved, onCancel }: Props) {
  const [name, setName] = useState(profile?.name ?? '');
  const [changes, setChanges] = useState<DraftChange[]>(
    () => (profile?.changes ?? []).map(toDraft),
  );
  const [addKind, setAddKind] = useState<ChangeKind>('game-mode');
  const [nameError, setNameError] = useState<string | null>(null);
  const [changeErrors, setChangeErrors] = useState<Record<string, string[]>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  function addChange() {
    setChanges((prev) => [
      ...prev,
      { localId: nextLocalId(), kind: addKind, params: defaultParams(addKind) },
    ]);
  }

  function updateParam(localId: string, key: string, value: string) {
    setChanges((prev) =>
      prev.map((c) =>
        c.localId === localId ? { ...c, params: { ...c.params, [key]: value } } : c,
      ),
    );
  }

  function removeChange(localId: string) {
    setChanges((prev) => prev.filter((c) => c.localId !== localId));
  }

  async function handleSave() {
    const errors: Record<string, string[]> = {};
    const nameErr = validateProfileName(name);
    setNameError(nameErr);
    for (const change of changes) {
      const errs = validateChangeParams(change.kind, change.params);
      if (errs.length > 0) errors[change.localId] = errs;
    }
    setChangeErrors(errors);
    if (nameErr || Object.keys(errors).length > 0 || changes.length === 0) {
      setFormError(
        changes.length === 0
          ? 'Add at least one change before saving the profile.'
          : 'Fix the highlighted problems before saving.',
      );
      return;
    }
    setFormError(null);
    setSaving(true);
    try {
      const payload = {
        name: name.trim(),
        changes: changes.map((c) => ({ kind: c.kind, params: c.params })),
      };
      if (profile) {
        await updateProfile({ id: profile.id, ...payload });
      } else {
        await createProfile(payload);
      }
      onSaved();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="editor">
      <div className="field">
        <label htmlFor="profile-name">Profile name</label>
        <input
          id="profile-name"
          type="text"
          value={name}
          maxLength={80}
          onChange={(e) => setName(e.target.value)}
          placeholder="e.g. Elden Ring — high performance"
        />
        {nameError && (
          <p className="field-error" role="alert">
            {nameError}
          </p>
        )}
      </div>

      <h3>Changes ({changes.length})</h3>
      {changes.length === 0 && (
        <p className="muted">
          No changes yet. Pick a change type below and add it to the profile.
        </p>
      )}
      <ul className="draft-list">
        {changes.map((change) => (
          <li key={change.localId} className="draft-card">
            <ChangeForm
              change={change}
              errors={changeErrors[change.localId] ?? []}
              onParam={(key, value) => updateParam(change.localId, key, value)}
              onRemove={() => removeChange(change.localId)}
            />
          </li>
        ))}
      </ul>

      <div className="add-change">
        <label htmlFor="add-kind">Add change</label>
        <div className="add-change-row">
          <select
            id="add-kind"
            value={addKind}
            onChange={(e) => setAddKind(e.target.value as ChangeKind)}
          >
            {CHANGE_KIND_META.map((m) => (
              <option key={m.kind} value={m.kind}>
                {m.label}
              </option>
            ))}
          </select>
          <button type="button" className="btn" onClick={addChange}>
            Add
          </button>
        </div>
        <p className="muted small">
          {CHANGE_KIND_META.find((m) => m.kind === addKind)?.description}
        </p>
      </div>

      {formError && (
        <div className="alert alert-error" role="alert">
          {formError}
        </div>
      )}

      <div className="modal-actions">
        <button type="button" className="btn" onClick={onCancel}>
          Cancel
        </button>
        <button
          type="button"
          className="btn btn-primary"
          onClick={() => void handleSave()}
          disabled={saving}
        >
          {saving ? 'Saving…' : profile ? 'Save changes' : 'Create profile'}
        </button>
      </div>
    </div>
  );
}

interface ChangeFormProps {
  change: DraftChange;
  errors: string[];
  onParam: (key: string, value: string) => void;
  onRemove: () => void;
}

function ChangeForm({ change, errors, onParam, onRemove }: ChangeFormProps) {
  const meta = CHANGE_KIND_META.find((m) => m.kind === change.kind);
  const idPrefix = `chg-${change.localId}`;
  return (
    <div>
      <div className="draft-head">
        <strong>{meta?.label ?? change.kind}</strong>
        <button
          type="button"
          className="btn btn-danger btn-sm"
          onClick={onRemove}
          aria-label={`Remove ${meta?.label ?? change.kind} change`}
        >
          Remove
        </button>
      </div>

      {change.kind === 'game-mode' && (
        <div className="field">
          <label htmlFor={`${idPrefix}-enabled`}>Game Mode</label>
          <select
            id={`${idPrefix}-enabled`}
            value={change.params['enabled'] ?? 'true'}
            onChange={(e) => onParam('enabled', e.target.value)}
          >
            <option value="true">On</option>
            <option value="false">Off</option>
          </select>
        </div>
      )}

      {change.kind === 'power-plan' && (
        <div className="field">
          <label htmlFor={`${idPrefix}-guid`}>Power-plan GUID</label>
          <input
            id={`${idPrefix}-guid`}
            type="text"
            value={change.params['guid'] ?? ''}
            onChange={(e) => onParam('guid', e.target.value.trimStart())}
            placeholder="381b4222-f694-41f0-9685-ff5bb260df2e"
            aria-describedby={`${idPrefix}-guid-hint`}
            spellCheck={false}
          />
          <p className="hint" id={`${idPrefix}-guid-hint`}>
            You must pick your own plan: open a terminal and run{' '}
            <code>powercfg /list</code>, then paste the GUID of the plan you
            want. Format: 8-4-4-4-12 hexadecimal characters.
          </p>
        </div>
      )}

      {change.kind === 'process-priority' && (
        <>
          <div className="field">
            <label htmlFor={`${idPrefix}-process`}>Process name</label>
            <input
              id={`${idPrefix}-process`}
              type="text"
              value={change.params['process'] ?? ''}
              onChange={(e) => onParam('process', e.target.value.trimStart())}
              placeholder="game.exe"
              spellCheck={false}
            />
          </div>
          <div className="field">
            <label htmlFor={`${idPrefix}-priority`}>Priority</label>
            <select
              id={`${idPrefix}-priority`}
              value={change.params['priority'] ?? 'above-normal'}
              onChange={(e) => onParam('priority', e.target.value)}
            >
              {PRIORITY_OPTIONS.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
            <p className="hint">
              Only above-normal and high are offered. Realtime priority is never
              allowed — it can starve the OS itself.
            </p>
          </div>
        </>
      )}

      {change.kind === 'fullscreen-optimizations' && (
        <>
          <div className="field">
            <label htmlFor={`${idPrefix}-exepath`}>Game .exe path</label>
            <input
              id={`${idPrefix}-exepath`}
              type="text"
              value={change.params['exePath'] ?? ''}
              onChange={(e) => onParam('exePath', e.target.value.trimStart())}
              placeholder="C:\Games\MyGame\game.exe"
              spellCheck={false}
            />
          </div>
          <div className="field">
            <label htmlFor={`${idPrefix}-fso`}>Fullscreen optimizations</label>
            <select
              id={`${idPrefix}-fso`}
              value={change.params['enabled'] ?? 'false'}
              onChange={(e) => onParam('enabled', e.target.value)}
            >
              <option value="true">On</option>
              <option value="false">Off</option>
            </select>
          </div>
        </>
      )}

      {errors.length > 0 && (
        <ul className="field-error-list" role="alert">
          {errors.map((e, i) => (
            <li key={i}>{e}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
