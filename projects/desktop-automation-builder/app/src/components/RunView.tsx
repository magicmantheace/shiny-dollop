import { useCallback, useEffect, useState } from 'react';
import type {
  PreviewAction,
  Run,
  RunStatus,
  Workflow,
} from '../../shared/types';
import { dabErrorMessage, getDab } from '../lib/dab';
import { ErrorBanner, StatusBadge, formatDateTime } from './ui';

interface Props {
  workflowId: string;
  onBack: () => void;
}

const ACTIVE_STATUSES: RunStatus[] = ['pending', 'awaiting-approval', 'running'];
const POLL_INTERVAL_MS = 1000;

export function RunView({ workflowId, onBack }: Props) {
  const [workflow, setWorkflow] = useState<Workflow | null>(null);
  const [runs, setRuns] = useState<Run[]>([]);
  const [activeRun, setActiveRun] = useState<Run | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [previewActions, setPreviewActions] = useState<PreviewAction[]>([]);
  const [showApproval, setShowApproval] = useState(false);
  const [approved, setApproved] = useState(false);
  const [starting, setStarting] = useState(false);
  const [cancelling, setCancelling] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const dab = getDab();
      const [wf, history] = await Promise.all([
        dab.workflowsGet(workflowId),
        dab.runsList(workflowId),
      ]);
      if (!wf) {
        setError(`Workflow not found (id: ${workflowId}).`);
        return;
      }
      setWorkflow(wf);
      setRuns(history);
      const latest = history[0];
      if (latest) setActiveRun(latest);
    } catch (e) {
      setError(dabErrorMessage(e));
    } finally {
      setLoading(false);
    }
  }, [workflowId]);

  useEffect(() => {
    void load();
  }, [load]);

  // Poll the active run while it is in flight.
  useEffect(() => {
    if (!activeRun || !ACTIVE_STATUSES.includes(activeRun.status)) return;
    const runId = activeRun.id;
    const timer = window.setInterval(() => {
      getDab()
        .runsGet(runId)
        .then((fresh) => {
          if (!fresh) return;
          setActiveRun(fresh);
          setRuns((prev) =>
            prev.map((r) => (r.id === fresh.id ? fresh : r)),
          );
        })
        .catch(() => {
          /* keep polling; transient read failures should not kill the view */
        });
    }, POLL_INTERVAL_MS);
    return () => window.clearInterval(timer);
  }, [activeRun?.id, activeRun?.status]);

  function upsertRun(run: Run) {
    setActiveRun(run);
    setRuns((prev) => [
      run,
      ...prev.filter((r) => r.id !== run.id),
    ]);
  }

  async function handlePreview() {
    setError('');
    try {
      const actions = await getDab().runsPreview(workflowId);
      setPreviewActions(actions);
      setApproved(false);
      setShowApproval(true);
    } catch (e) {
      setError(dabErrorMessage(e));
    }
  }

  async function handleApproveAndRun() {
    if (!approved) return;
    setStarting(true);
    setError('');
    try {
      const run = await getDab().runsStart(workflowId, true);
      setShowApproval(false);
      upsertRun(run);
    } catch (e) {
      setError(dabErrorMessage(e));
    } finally {
      setStarting(false);
    }
  }

  async function handleCancel() {
    if (!activeRun) return;
    setCancelling(true);
    setError('');
    try {
      upsertRun(await getDab().runsCancel(activeRun.id));
    } catch (e) {
      setError(dabErrorMessage(e));
    } finally {
      setCancelling(false);
    }
  }

  async function handleRetry() {
    if (!activeRun) return;
    setError('');
    try {
      upsertRun(await getDab().runsRetry(activeRun.id));
    } catch (e) {
      setError(dabErrorMessage(e));
    }
  }

  if (loading) return <p>Loading run view…</p>;

  const isActive =
    !!activeRun && ACTIVE_STATUSES.includes(activeRun.status);

  return (
    <section aria-labelledby="run-heading">
      <div className="section-head">
        <h2 id="run-heading">
          Run{workflow ? ` — ${workflow.name}` : ''}
        </h2>
        <div className="section-actions">
          <button type="button" onClick={onBack}>
            Back to workflows
          </button>
          <button
            type="button"
            className="primary"
            onClick={() => void handlePreview()}
          >
            Preview
          </button>
        </div>
      </div>

      <ErrorBanner message={error} onDismiss={() => setError('')} />

      {showApproval && (
        <div
          className="modal-overlay"
          onClick={() => !starting && setShowApproval(false)}
        >
          <div
            className="modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="approval-title"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 id="approval-title">Review planned actions</h2>
            <p className="muted">
              This is a dry-run preview. Nothing has been changed yet.
            </p>
            {previewActions.length === 0 ? (
              <p className="muted">No actions planned.</p>
            ) : (
              <ol className="preview-list">
                {previewActions.map((a) => (
                  <li key={a.stepId}>
                    <strong>{a.label}</strong>
                    <span className="muted"> — {a.description}</span>
                  </li>
                ))}
              </ol>
            )}
            <label className="approval-check">
              <input
                type="checkbox"
                checked={approved}
                onChange={(e) => setApproved(e.target.checked)}
              />
              I have reviewed the planned actions and approve this run
            </label>
            <div className="modal-actions">
              <button
                type="button"
                disabled={starting}
                onClick={() => setShowApproval(false)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="primary"
                disabled={!approved || starting}
                onClick={() => void handleApproveAndRun()}
              >
                {starting ? 'Starting…' : 'Approve & run'}
              </button>
            </div>
          </div>
        </div>
      )}

      {runs.length > 0 && (
        <div className="panel">
          <h3>Run history</h3>
          <ul className="run-history">
            {runs.map((r) => (
              <li key={r.id}>
                <button
                  type="button"
                  className={r.id === activeRun?.id ? 'selected' : ''}
                  onClick={() => setActiveRun(r)}
                  aria-current={r.id === activeRun?.id ? 'true' : undefined}
                >
                  <span className="mono">{r.id.slice(0, 8)}</span>{' '}
                  <StatusBadge status={r.status} />{' '}
                  <span className="muted small">
                    v{r.workflowVersion}
                    {r.startedAt ? ` · ${formatDateTime(r.startedAt)}` : ''}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {activeRun ? (
        <div className="panel">
          <div className="section-head">
            <h3>
              Run <span className="mono">{activeRun.id}</span>{' '}
              <StatusBadge status={activeRun.status} />
            </h3>
            <div className="section-actions">
              {isActive && (
                <button
                  type="button"
                  className="danger"
                  disabled={cancelling}
                  onClick={() => void handleCancel()}
                >
                  {cancelling ? 'Cancelling…' : 'Cancel run'}
                </button>
              )}
              {activeRun.status === 'failed' && (
                <button type="button" onClick={() => void handleRetry()}>
                  Retry from failed step
                </button>
              )}
            </div>
          </div>

          {activeRun.steps.length === 0 ? (
            <p className="muted">No step activity recorded yet.</p>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">Step</th>
                  <th scope="col">Kind</th>
                  <th scope="col">Outcome</th>
                  <th scope="col">Detail</th>
                </tr>
              </thead>
              <tbody>
                {activeRun.steps.map((s) => (
                  <tr key={s.stepId}>
                    <td>{s.label}</td>
                    <td>{s.kind}</td>
                    <td>
                      <StatusBadge status={s.outcome} />
                    </td>
                    <td>{s.detail ?? ''}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      ) : (
        <p className="muted">
          No runs yet. Use <strong>Preview</strong> to review the planned
          actions, then approve to run.
        </p>
      )}
    </section>
  );
}
