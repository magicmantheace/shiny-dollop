import { useEffect, useRef, useState } from 'react';
import type {
  ActivationProgress,
  ActivationResult,
  PlannedChange,
  Profile,
} from '../../shared/gpp-types';
import { activateProfile, onActivationProgress, previewProfile } from '../gpp';
import { CHANGE_KIND_META } from '../validation';

interface Props {
  profile: Profile;
  onClose: () => void;
  onChanged: () => void;
}

type Stage = 'preview' | 'activating' | 'done';

function kindLabel(kind: string): string {
  return CHANGE_KIND_META.find((m) => m.kind === kind)?.label ?? kind;
}

export function PreviewModal({ profile, onClose, onChanged }: Props) {
  const [stage, setStage] = useState<Stage>('preview');
  const [planned, setPlanned] = useState<PlannedChange[] | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [previewLoading, setPreviewLoading] = useState(true);
  const [approved, setApproved] = useState(false);
  const [progress, setProgress] = useState<ActivationProgress[]>([]);
  const [result, setResult] = useState<ActivationResult | null>(null);
  const [activateError, setActivateError] = useState<string | null>(null);
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    closeRef.current?.focus();
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  useEffect(() => {
    let cancelled = false;
    setPreviewLoading(true);
    setPreviewError(null);
    void previewProfile(profile.id)
      .then((p) => {
        if (!cancelled) setPlanned(p);
      })
      .catch((err: unknown) => {
        if (!cancelled)
          setPreviewError(err instanceof Error ? err.message : String(err));
      })
      .finally(() => {
        if (!cancelled) setPreviewLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [profile.id]);

  const unsupported = planned?.filter((p) => !p.supported) ?? [];
  const allSupported = (planned?.length ?? 0) > 0 && unsupported.length === 0;
  const canActivate = approved && allSupported && stage === 'preview';

  async function handleActivate() {
    if (!canActivate) return;
    setStage('activating');
    setProgress([]);
    setActivateError(null);
    const unsubscribe = onActivationProgress((evt) =>
      setProgress((prev) => [...prev, evt]),
    );
    try {
      const res = await activateProfile(profile.id, true);
      setResult(res);
    } catch (err) {
      setActivateError(err instanceof Error ? err.message : String(err));
    } finally {
      unsubscribe();
      setStage('done');
      onChanged();
    }
  }

  return (
    <div className="modal-backdrop">
      <div
        className="modal modal-wide"
        role="dialog"
        aria-modal="true"
        aria-labelledby="preview-title"
      >
        <h2 id="preview-title">Preview — {profile.name}</h2>

        {previewLoading && <p role="status">Loading preview…</p>}
        {previewError && (
          <div className="alert alert-error" role="alert">
            {previewError}
          </div>
        )}

        {planned && stage === 'preview' && (
          <>
            {planned.length === 0 ? (
              <div className="empty" role="status">
                <p>This profile has no changes to preview.</p>
              </div>
            ) : (
              <table className="table">
                <thead>
                  <tr>
                    <th scope="col">Change</th>
                    <th scope="col">Target</th>
                    <th scope="col">From → To</th>
                    <th scope="col">Reversible</th>
                    <th scope="col">Support</th>
                  </tr>
                </thead>
                <tbody>
                  {planned.map((p) => (
                    <tr key={p.changeId}>
                      <td>{kindLabel(p.kind)}</td>
                      <td>{p.target}</td>
                      <td>
                        <span className="from">{p.from}</span>
                        {' → '}
                        <span className="to">{p.to}</span>
                      </td>
                      <td>
                        {p.reversible ? (
                          <span className="badge badge-ok">reversible</span>
                        ) : (
                          <span className="badge badge-warn">
                            not reversible
                          </span>
                        )}
                      </td>
                      <td>
                        {p.supported ? (
                          <span className="badge badge-ok">supported</span>
                        ) : (
                          <span
                            className="badge badge-bad"
                            title={p.unsupportedReason ?? 'Not supported'}
                          >
                            unsupported: {p.unsupportedReason ?? 'no reason given'}
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}

            {unsupported.length > 0 && (
              <div className="alert alert-error" role="alert">
                <strong>Activation is blocked.</strong> {unsupported.length}{' '}
                {unsupported.length === 1 ? 'change is' : 'changes are'} not
                supported on this machine:
                <ul>
                  {unsupported.map((p) => (
                    <li key={p.changeId}>
                      {kindLabel(p.kind)} on {p.target} —{' '}
                      {p.unsupportedReason ?? 'no reason given'}
                    </li>
                  ))}
                </ul>
                Remove or fix these changes in the profile editor before
                activating.
              </div>
            )}

            {planned.length > 0 && (
              <div className="approval">
                <label className="checkbox-row">
                  <input
                    type="checkbox"
                    checked={approved}
                    onChange={(e) => setApproved(e.target.checked)}
                  />
                  <span>
                    I understand these changes and approve applying them to my
                    system.
                  </span>
                </label>
              </div>
            )}
          </>
        )}

        {stage === 'activating' && (
          <div role="status" aria-live="polite">
            <p>Activating — applying changes one by one…</p>
            <ul className="progress-list">
              {progress.map((evt, i) => (
                <li key={i}>
                  <span className={`phase phase-${evt.phase}`}>
                    {evt.phase.replace('-', ' ')}
                  </span>{' '}
                  {kindLabel(evt.kind)} — {evt.target} ({evt.index + 1} of{' '}
                  {evt.total})
                </li>
              ))}
            </ul>
          </div>
        )}

        {stage === 'done' && (
          <div>
            {activateError && (
              <div className="alert alert-error" role="alert">
                {activateError}
              </div>
            )}
            {result && <ActivationResultView result={result} />}
          </div>
        )}

        <div className="modal-actions">
          <button
            ref={closeRef}
            type="button"
            className="btn"
            onClick={onClose}
          >
            {stage === 'preview' ? 'Cancel' : 'Close'}
          </button>
          {stage === 'preview' && planned && planned.length > 0 && (
            <button
              type="button"
              className="btn btn-primary"
              disabled={!canActivate}
              onClick={() => void handleActivate()}
              title={
                !allSupported
                  ? 'Resolve unsupported changes first'
                  : !approved
                    ? 'Tick the approval checkbox first'
                    : 'Apply these changes'
              }
            >
              Activate
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export function ActivationResultView({ result }: { result: ActivationResult }) {
  return (
    <div
      className={`alert ${result.ok ? 'alert-ok' : 'alert-error'}`}
      role="status"
    >
      {result.ok ? (
        <p>
          <strong>Activation complete.</strong> Applied {result.applied.length}{' '}
          {result.applied.length === 1 ? 'change' : 'changes'}.
        </p>
      ) : (
        <p>
          <strong>Activation failed.</strong>{' '}
          {result.error ?? 'An unknown error occurred.'}
        </p>
      )}
      {result.applied.length > 0 && (
        <p className="muted small">
          Journal entries applied: {result.applied.join(', ')}
        </p>
      )}
      {result.rolledBack.length > 0 && (
        <p>
          <strong>Automatic rollback:</strong> {result.rolledBack.length}{' '}
          {result.rolledBack.length === 1 ? 'change was' : 'changes were'}{' '}
          automatically rolled back to keep your system consistent (
          {result.rolledBack.join(', ')}).
        </p>
      )}
      {result.skipped.length > 0 && (
        <div>
          <p>
            <strong>Skipped:</strong>
          </p>
          <ul>
            {result.skipped.map((s) => (
              <li key={s.changeId}>
                {kindLabel(s.kind)} — {s.target}: {s.reason}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
