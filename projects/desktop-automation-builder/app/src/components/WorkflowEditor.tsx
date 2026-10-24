import { useCallback, useEffect, useState } from 'react';
import type {
  ApprovedScript,
  Step,
  StepKind,
  Workflow,
} from '../../shared/types';
import { dabErrorMessage, getDab } from '../lib/dab';
import { describeStep, newStep, STEP_KINDS, stepKindLabel } from '../lib/steps';
import { ConfirmDialog, ErrorBanner, formatDateTime } from './ui';

interface Props {
  workflowId: string;
  onBack: () => void;
  onRun: (workflowId: string) => void;
}

function StepFields({
  step,
  scripts,
  onPatch,
}: {
  step: Step;
  scripts: ApprovedScript[];
  onPatch: (patch: Partial<Step>) => void;
}) {
  switch (step.kind) {
    case 'file-copy':
      return (
        <>
          <label>
            From
            <input
              type="text"
              value={step.from}
              onChange={(e) => onPatch({ from: e.target.value })}
              placeholder="Relative to sandbox root, e.g. reports/weekly.txt"
            />
          </label>
          <label>
            To
            <input
              type="text"
              value={step.to}
              onChange={(e) => onPatch({ to: e.target.value })}
              placeholder="Relative to sandbox root, e.g. backup/weekly.txt"
            />
          </label>
        </>
      );
    case 'file-move-to-trash':
      return (
        <label>
          Path to move
          <input
            type="text"
            value={step.path}
            onChange={(e) => onPatch({ path: e.target.value })}
            placeholder="Relative to sandbox root"
          />
        </label>
      );
    case 'folder-create':
      return (
        <label>
          Folder path
          <input
            type="text"
            value={step.path}
            onChange={(e) => onPatch({ path: e.target.value })}
            placeholder="Relative to sandbox root"
          />
        </label>
      );
    case 'run-approved-script':
      return (
        <>
          <label>
            Script
            <select
              value={step.scriptId}
              onChange={(e) => onPatch({ scriptId: e.target.value })}
            >
              <option value="">— Select an approved script —</option>
              {scripts.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </label>
          <p className="muted small">
            Only scripts you explicitly register can run.
          </p>
          <label>
            Arguments (one per line)
            <textarea
              rows={3}
              value={step.args.join('\n')}
              onChange={(e) => onPatch({ args: e.target.value.split('\n') })}
              placeholder="--fast&#10;--output report.txt"
            />
          </label>
        </>
      );
    case 'log-message':
      return (
        <label>
          Message
          <textarea
            rows={2}
            value={step.message}
            onChange={(e) => onPatch({ message: e.target.value })}
            placeholder="Message written to the run log"
          />
        </label>
      );
  }
}

export function WorkflowEditor({ workflowId, onBack, onRun }: Props) {
  const [workflow, setWorkflow] = useState<Workflow | null>(null);
  const [name, setName] = useState('');
  const [sandboxRoot, setSandboxRoot] = useState('');
  const [steps, setSteps] = useState<Step[]>([]);
  const [scripts, setScripts] = useState<ApprovedScript[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [savedMsg, setSavedMsg] = useState('');
  const [dirty, setDirty] = useState(false);
  const [addKind, setAddKind] = useState<StepKind>('file-copy');
  const [removeTarget, setRemoveTarget] = useState<Step | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const dab = getDab();
      const [wf, scriptList] = await Promise.all([
        dab.workflowsGet(workflowId),
        dab.scriptsList(),
      ]);
      if (!wf) {
        setError(`Workflow not found (id: ${workflowId}).`);
        return;
      }
      setWorkflow(wf);
      setName(wf.name);
      setSandboxRoot(wf.sandboxRoot);
      setSteps(wf.steps);
      setScripts(scriptList);
      setDirty(false);
    } catch (e) {
      setError(dabErrorMessage(e));
    } finally {
      setLoading(false);
    }
  }, [workflowId]);

  useEffect(() => {
    void load();
  }, [load]);

  function patchStep(id: string, patch: Partial<Step>) {
    setSteps((prev) =>
      prev.map((s) => (s.id === id ? ({ ...s, ...patch } as Step) : s)),
    );
    setDirty(true);
    setSavedMsg('');
  }

  function addStep() {
    setSteps((prev) => [...prev, newStep(addKind)]);
    setDirty(true);
    setSavedMsg('');
  }

  function moveStep(id: string, dir: -1 | 1) {
    setSteps((prev) => {
      const i = prev.findIndex((s) => s.id === id);
      const j = i + dir;
      if (i < 0 || j < 0 || j >= prev.length) return prev;
      const a = prev[i];
      const b = prev[j];
      if (!a || !b) return prev;
      const next = [...prev];
      next[i] = b;
      next[j] = a;
      return next;
    });
    setDirty(true);
    setSavedMsg('');
  }

  function confirmRemoveStep() {
    if (!removeTarget) return;
    setSteps((prev) => prev.filter((s) => s.id !== removeTarget.id));
    setRemoveTarget(null);
    setDirty(true);
    setSavedMsg('');
  }

  async function handleBrowse() {
    setError('');
    try {
      const dir = await getDab().pickDirectory();
      if (dir) {
        setSandboxRoot(dir);
        setDirty(true);
        setSavedMsg('');
      }
    } catch (e) {
      setError(dabErrorMessage(e));
    }
  }

  async function handleSave() {
    setSaving(true);
    setError('');
    setSavedMsg('');
    try {
      const updated = await getDab().workflowsUpdate(workflowId, {
        name: name.trim() || 'Untitled workflow',
        sandboxRoot,
        steps,
      });
      setWorkflow(updated);
      setDirty(false);
      setSavedMsg(`Saved — now at version ${updated.version}.`);
    } catch (e) {
      setError(dabErrorMessage(e));
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <p>Loading workflow…</p>;

  return (
    <section aria-labelledby="editor-heading">
      <div className="section-head">
        <h2 id="editor-heading">Workflow editor</h2>
        <div className="section-actions">
          <button type="button" onClick={onBack}>
            Back to workflows
          </button>
          <button
            type="button"
            className="primary"
            onClick={() => onRun(workflowId)}
          >
            Preview &amp; run
          </button>
        </div>
      </div>

      <ErrorBanner message={error} onDismiss={() => setError('')} />
      {savedMsg && (
        <p className="success-banner" role="status">
          {savedMsg}
        </p>
      )}

      {workflow && (
        <>
          <div className="panel">
            <label>
              Name
              <input
                type="text"
                value={name}
                onChange={(e) => {
                  setName(e.target.value);
                  setDirty(true);
                }}
              />
            </label>
            <label>
              Sandbox root
              <span className="field-row">
                <input
                  type="text"
                  value={sandboxRoot}
                  onChange={(e) => {
                    setSandboxRoot(e.target.value);
                    setDirty(true);
                  }}
                  placeholder="Folder all workflow paths are relative to"
                />
                <button type="button" onClick={() => void handleBrowse()}>
                  Browse…
                </button>
              </span>
            </label>
            <p className="muted small">
              All step paths are relative to this folder. Currently editing
              version {workflow.version}.
              {dirty && <strong> Unsaved changes.</strong>}
            </p>
          </div>

          <div className="section-head">
            <h3>Steps ({steps.length})</h3>
            <div className="section-actions">
              <label className="inline-label">
                Add step of kind
                <select
                  value={addKind}
                  onChange={(e) => setAddKind(e.target.value as StepKind)}
                >
                  {STEP_KINDS.map((k) => (
                    <option key={k.kind} value={k.kind}>
                      {k.label}
                    </option>
                  ))}
                </select>
              </label>
              <button type="button" onClick={addStep}>
                Add step
              </button>
            </div>
          </div>

          {steps.length === 0 ? (
            <p className="muted">
              No steps yet. Add your first step above.
            </p>
          ) : (
            <ol className="step-list">
              {steps.map((step, index) => (
                <li key={step.id}>
                  <fieldset
                    className="step-card"
                    data-testid={`step-${step.id}`}
                  >
                    <legend>
                      {index + 1}. {stepKindLabel(step.kind)}
                      {step.label ? ` — ${step.label}` : ''}
                    </legend>
                    <label>
                      Step label
                      <input
                        type="text"
                        value={step.label}
                        onChange={(e) =>
                          patchStep(step.id, { label: e.target.value })
                        }
                        placeholder="Short description of this step"
                      />
                    </label>
                    <StepFields
                      step={step}
                      scripts={scripts}
                      onPatch={(patch) => patchStep(step.id, patch)}
                    />
                    <p className="muted small">{describeStep(step)}</p>
                    <div className="step-actions">
                      <button
                        type="button"
                        onClick={() => moveStep(step.id, -1)}
                        disabled={index === 0}
                        aria-label={`Move step "${step.label || stepKindLabel(step.kind)}" up`}
                      >
                        Move up
                      </button>
                      <button
                        type="button"
                        onClick={() => moveStep(step.id, 1)}
                        disabled={index === steps.length - 1}
                        aria-label={`Move step "${step.label || stepKindLabel(step.kind)}" down`}
                      >
                        Move down
                      </button>
                      <button
                        type="button"
                        className="danger-text"
                        onClick={() => setRemoveTarget(step)}
                        aria-label={`Remove step "${step.label || stepKindLabel(step.kind)}"`}
                      >
                        Remove
                      </button>
                    </div>
                  </fieldset>
                </li>
              ))}
            </ol>
          )}

          <div className="form-actions">
            <button
              type="button"
              className="primary"
              disabled={saving || !dirty}
              onClick={() => void handleSave()}
            >
              {saving ? 'Saving…' : 'Save workflow'}
            </button>
            <span className="muted small">
              Saving bumps the version and snapshots the current steps.
            </span>
          </div>

          <h3>Version history</h3>
          {workflow.versions.length === 0 ? (
            <p className="muted">No saved versions yet.</p>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">Version</th>
                  <th scope="col">Name</th>
                  <th scope="col">Steps</th>
                  <th scope="col">Created</th>
                </tr>
              </thead>
              <tbody>
                {[...workflow.versions]
                  .sort((a, b) => b.version - a.version)
                  .map((v) => (
                    <tr key={v.version}>
                      <td>v{v.version}</td>
                      <td>{v.name}</td>
                      <td>{v.steps.length}</td>
                      <td>{formatDateTime(v.createdAt)}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          )}

          {removeTarget && (
            <ConfirmDialog
              title={`Remove step "${removeTarget.label || stepKindLabel(removeTarget.kind)}"?`}
              body={<p>{describeStep(removeTarget)}</p>}
              confirmLabel="Remove step"
              danger
              onConfirm={confirmRemoveStep}
              onCancel={() => setRemoveTarget(null)}
            />
          )}
        </>
      )}
    </section>
  );
}
