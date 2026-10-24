import { useCallback, useEffect, useRef, useState } from 'react';
import type {
  AdapterMode,
  AuditEntry,
  EndpointConfig,
  HealthResult,
  Proposal,
  ResourceSnapshot,
  Task,
  TaskLogEntry,
} from '../../shared/types';
import { MAX_PROMPT_CHARS } from '../../shared/types';
import { lacc, laccErrorInfo } from '../lib/lacc';

interface ApiError {
  code: string;
  message: string;
}

const DEFAULT_CONFIG: EndpointConfig = {
  mode: 'mock',
  baseUrl: 'http://127.0.0.1:11434',
  model: '',
  timeoutMs: 30_000,
  workspaceRoot: '',
};

export function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return 'unknown';
  const gib = bytes / 1024 ** 3;
  if (gib >= 1) return `${gib.toFixed(2)} GiB`;
  const mib = bytes / 1024 ** 2;
  if (mib >= 1) return `${mib.toFixed(2)} MiB`;
  return `${bytes} B`;
}

export function formatTime(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString();
}

function excerpt(text: string, max = 90): string {
  const flat = text.replace(/\s+/g, ' ').trim();
  return flat.length > max ? `${flat.slice(0, max)}…` : flat;
}

export function App() {
  const [apiError, setApiError] = useState<ApiError | null>(null);

  // Endpoint / config
  const [config, setConfig] = useState<EndpointConfig>(DEFAULT_CONFIG);
  const [models, setModels] = useState<string[]>([]);
  const [health, setHealth] = useState<HealthResult | null>(null);
  const [resources, setResources] = useState<ResourceSnapshot | null>(null);
  const [savedNote, setSavedNote] = useState<string | null>(null);

  // Tasks
  const [prompt, setPrompt] = useState('');
  const [tasks, setTasks] = useState<Task[]>([]);
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [taskLogs, setTaskLogs] = useState<TaskLogEntry[]>([]);

  // Proposals
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [selectedProposalId, setSelectedProposalId] = useState<string | null>(
    null,
  );

  // Audit
  const [audit, setAudit] = useState<AuditEntry[]>([]);

  const selectedTaskIdRef = useRef<string | null>(null);
  selectedTaskIdRef.current = selectedTaskId;

  // Snapshot of the task list as of the last render, so the polling loop can
  // detect a queued/running -> terminal transition (proposals and audit
  // entries are created at completion, so they must be refreshed then).
  const tasksRef = useRef<Task[]>([]);
  tasksRef.current = tasks;

  const reportError = useCallback((err: unknown) => {
    setApiError(laccErrorInfo(err));
  }, []);

  const refreshTasks = useCallback(async () => {
    try {
      const list = await lacc().tasksList();
      setTasks(list);
      return list;
    } catch (err) {
      reportError(err);
      return null;
    }
  }, [reportError]);

  const refreshProposals = useCallback(async () => {
    try {
      const list = await lacc().proposalsList();
      setProposals(list);
      return list;
    } catch (err) {
      reportError(err);
      return null;
    }
  }, [reportError]);

  const refreshAudit = useCallback(async () => {
    try {
      setAudit(await lacc().auditList(50));
    } catch (err) {
      reportError(err);
    }
  }, [reportError]);

  const refreshLogs = useCallback(
    async (taskId: string) => {
      try {
        setTaskLogs(await lacc().tasksLogs(taskId));
      } catch (err) {
        reportError(err);
      }
    },
    [reportError],
  );

  const checkHealth = useCallback(async () => {
    try {
      const result = await lacc().endpointHealth();
      setHealth(result);
      if (result.models.length > 0) {
        setModels((prev) => Array.from(new Set([...prev, ...result.models])));
      }
      return result;
    } catch (err) {
      reportError(err);
      return null;
    }
  }, [reportError]);

  // Initial load: config, resources, health, models, tasks, proposals, audit.
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const saved = await lacc().configGet();
        if (!cancelled && saved) setConfig(saved);
      } catch (err) {
        if (!cancelled) reportError(err);
      }
      try {
        const snap = await lacc().resourcesSnapshot();
        if (!cancelled) setResources(snap);
      } catch (err) {
        if (!cancelled) reportError(err);
      }
      try {
        const list = await lacc().endpointModels();
        if (!cancelled && list.length > 0) setModels(list);
      } catch {
        // Models are best-effort: the free-text fallback covers failures,
        // and Check health surfaces the actionable endpoint error.
      }
      if (!cancelled) {
        await checkHealth();
        await refreshTasks();
        await refreshProposals();
        await refreshAudit();
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [checkHealth, refreshAudit, refreshProposals, refreshTasks, reportError]);

  const hasActiveTask = tasks.some(
    (t) => t.status === 'queued' || t.status === 'running',
  );

  // Poll while any task is queued/running.
  useEffect(() => {
    if (!hasActiveTask) return;
    const timer = setInterval(() => {
      void (async () => {
        const before = tasksRef.current;
        const list = await refreshTasks();
        if (list) {
          // A task finishing creates proposals (and audit entries) in the
          // engine, so observing a completion here must refresh both —
          // otherwise the UI keeps saying "No proposals yet" until a manual
          // refresh.
          const finished = list.some((t) => {
            const prev = before.find((b) => b.id === t.id);
            return (
              prev !== undefined &&
              (prev.status === 'queued' || prev.status === 'running') &&
              t.status !== 'queued' &&
              t.status !== 'running'
            );
          });
          if (finished) {
            await refreshProposals();
            await refreshAudit();
          }
        }
        const id = selectedTaskIdRef.current;
        if (id) await refreshLogs(id);
      })();
    }, 1000);
    return () => clearInterval(timer);
  }, [hasActiveTask, refreshAudit, refreshLogs, refreshProposals, refreshTasks]);

  const selectedTask = tasks.find((t) => t.id === selectedTaskId) ?? null;
  const selectedProposal =
    proposals.find((p) => p.id === selectedProposalId) ?? null;

  const selectTask = async (task: Task) => {
    setSelectedTaskId(task.id);
    try {
      const fresh = await lacc().tasksGet(task.id);
      setTasks((prev) => prev.map((t) => (t.id === fresh.id ? fresh : t)));
    } catch (err) {
      reportError(err);
    }
    await refreshLogs(task.id);
  };

  const onBrowse = async () => {
    try {
      const picked = await lacc().pickDirectory();
      if (picked) {
        setConfig((prev) => ({ ...prev, workspaceRoot: picked }));
      }
    } catch (err) {
      reportError(err);
    }
  };

  const onSave = async () => {
    setSavedNote(null);
    try {
      const saved = await lacc().configSave(config);
      setConfig(saved);
      setApiError(null);
      setSavedNote('Configuration saved.');
      await checkHealth();
      await refreshAudit();
    } catch (err) {
      reportError(err);
    }
  };

  const onSubmitTask = async () => {
    const trimmed = prompt.trim();
    if (!trimmed || prompt.length > MAX_PROMPT_CHARS) return;
    try {
      const task = await lacc().tasksSubmit({ prompt: trimmed });
      setApiError(null);
      setPrompt('');
      setTasks((prev) => [task, ...prev.filter((t) => t.id !== task.id)]);
      setSelectedTaskId(task.id);
      await refreshLogs(task.id);
      await refreshProposals();
      await refreshAudit();
    } catch (err) {
      reportError(err);
    }
  };

  const onCancelTask = async (task: Task) => {
    try {
      const updated = await lacc().tasksCancel(task.id);
      setTasks((prev) => prev.map((t) => (t.id === updated.id ? updated : t)));
      setApiError(null);
      await refreshAudit();
    } catch (err) {
      reportError(err);
    }
  };

  const decideProposal = async (proposal: Proposal, approve: boolean) => {
    try {
      const updated = approve
        ? await lacc().proposalsApprove(proposal.id)
        : await lacc().proposalsReject(proposal.id);
      setProposals((prev) =>
        prev.map((p) => (p.id === updated.id ? updated : p)),
      );
      setSelectedProposalId(updated.id);
      setApiError(null);
      await refreshAudit();
    } catch (err) {
      reportError(err);
    }
  };

  const promptTooLong = prompt.length > MAX_PROMPT_CHARS;

  return (
    <div className="app">
      <header className="app-header">
        <h1>Local AI Command Center</h1>
        <section aria-label="Resources" className="resource-strip">
          {resources ? (
            <ul className="resource-list">
              <li>
                CPU: {resources.cpuCount}{' '}
                {resources.cpuCount === 1 ? 'core' : 'cores'} —{' '}
                {resources.cpuModel}
              </li>
              <li>
                Load (1m):{' '}
                {resources.loadAvg1m === null
                  ? 'unavailable'
                  : resources.loadAvg1m.toFixed(2)}
              </li>
              <li>
                RAM: {formatBytes(resources.freeMemBytes)} free /{' '}
                {formatBytes(resources.totalMemBytes)} total
              </li>
              <li>GPU: unavailable — {resources.gpu.reason}</li>
            </ul>
          ) : (
            <p>Loading resources…</p>
          )}
        </section>
      </header>

      {apiError && (
        <div role="alert" className="error-banner">
          <strong>Error {apiError.code}:</strong> {apiError.message}
        </div>
      )}

      <main className="app-main">
        <section aria-labelledby="endpoint-heading" className="panel">
          <h2 id="endpoint-heading">Endpoint</h2>

          <label htmlFor="mode-select">Mode</label>
          <select
            id="mode-select"
            value={config.mode}
            onChange={(e) =>
              setConfig((prev) => ({
                ...prev,
                mode: e.target.value as AdapterMode,
              }))
            }
          >
            <option value="mock">Offline mock</option>
            <option value="live">Local endpoint</option>
          </select>

          <label htmlFor="base-url-input">Base URL</label>
          <input
            id="base-url-input"
            type="text"
            value={config.baseUrl}
            onChange={(e) =>
              setConfig((prev) => ({ ...prev, baseUrl: e.target.value }))
            }
            placeholder="http://127.0.0.1:11434"
          />

          <label htmlFor="model-input">Model</label>
          {models.length > 0 ? (
            <select
              id="model-input"
              value={config.model}
              onChange={(e) =>
                setConfig((prev) => ({ ...prev, model: e.target.value }))
              }
            >
              {config.model && !models.includes(config.model) && (
                <option value={config.model}>{config.model}</option>
              )}
              {models.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          ) : (
            <input
              id="model-input"
              type="text"
              value={config.model}
              onChange={(e) =>
                setConfig((prev) => ({ ...prev, model: e.target.value }))
              }
              placeholder="e.g. llama3"
            />
          )}

          <label htmlFor="timeout-input">Timeout (ms)</label>
          <input
            id="timeout-input"
            type="number"
            min={100}
            max={120000}
            value={config.timeoutMs}
            onChange={(e) =>
              setConfig((prev) => ({
                ...prev,
                timeoutMs: Number(e.target.value),
              }))
            }
          />

          <label htmlFor="workspace-input">Workspace root</label>
          <div className="inline-row">
            <input
              id="workspace-input"
              type="text"
              value={config.workspaceRoot}
              onChange={(e) =>
                setConfig((prev) => ({
                  ...prev,
                  workspaceRoot: e.target.value,
                }))
              }
              placeholder="/path/to/workspace"
            />
            <button type="button" onClick={() => void onBrowse()}>
              Browse…
            </button>
          </div>

          <div className="button-row">
            <button
              type="button"
              className="primary"
              onClick={() => void onSave()}
            >
              Save
            </button>
            <button type="button" onClick={() => void checkHealth()}>
              Check health
            </button>
          </div>
          {savedNote && <p className="note">{savedNote}</p>}

          {health &&
            (health.ok ? (
              <p className="health-ok">
                Endpoint OK — latency{' '}
                {health.latencyMs === null ? 'unknown' : `${health.latencyMs} ms`}{' '}
                — {health.models.length}{' '}
                {health.models.length === 1 ? 'model' : 'models'} available
                (mode: {health.mode}, checked {formatTime(health.checkedAt)}).
              </p>
            ) : (
              <div className="offline-banner">
                <h3>Endpoint offline</h3>
                <p>{health.message ?? 'The endpoint did not respond.'}</p>
                <p>
                  To fix this: start your local runtime (for example Ollama or
                  a compatible local server), check the URL above matches the
                  address and port it is listening on, then choose Check
                  health again. Or switch to Offline mock mode to explore the
                  app without a live endpoint.
                </p>
              </div>
            ))}
        </section>

        <section aria-labelledby="tasks-heading" className="panel">
          <h2 id="tasks-heading">Tasks</h2>

          <label htmlFor="prompt-input">Prompt</label>
          <textarea
            id="prompt-input"
            rows={5}
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="Ask the local model to do something in the workspace…"
          />
          <p className={promptTooLong ? 'char-count over' : 'char-count'}>
            {prompt.length} / {MAX_PROMPT_CHARS} characters
            {promptTooLong && ' — prompt is too long to submit.'}
          </p>
          <div className="button-row">
            <button
              type="button"
              className="primary"
              disabled={!prompt.trim() || promptTooLong}
              onClick={() => void onSubmitTask()}
            >
              Submit
            </button>
            <button
              type="button"
              onClick={() => {
                void refreshTasks();
                void refreshProposals();
                void refreshAudit();
              }}
            >
              Refresh
            </button>
          </div>

          {tasks.length === 0 ? (
            <p>No tasks yet.</p>
          ) : (
            <ul className="item-list">
              {tasks.map((task) => (
                <li key={task.id}>
                  <button
                    type="button"
                    className="item-button"
                    aria-current={task.id === selectedTaskId ? 'true' : undefined}
                    onClick={() => void selectTask(task)}
                  >
                    <span className={`badge status-${task.status}`}>
                      {task.status}
                    </span>{' '}
                    <span>{excerpt(task.prompt)}</span>{' '}
                    <span className="muted">
                      {task.model} · {formatTime(task.createdAt)}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}

          {selectedTask && (
            <div className="detail">
              <h3>Task detail</h3>
              <p>
                Status:{' '}
                <span className={`badge status-${selectedTask.status}`}>
                  {selectedTask.status}
                </span>{' '}
                · Model: {selectedTask.model} · Created:{' '}
                {formatTime(selectedTask.createdAt)}
              </p>
              <p className="muted">Prompt: {selectedTask.prompt}</p>
              {selectedTask.error && (
                <p className="task-error">Error: {selectedTask.error}</p>
              )}
              <h4>Output</h4>
              {selectedTask.output ? (
                <pre className="output">{selectedTask.output}</pre>
              ) : (
                <p>No output yet.</p>
              )}
              <h4>Log</h4>
              {taskLogs.length === 0 ? (
                <p>No log entries.</p>
              ) : (
                <ul className="log-list">
                  {taskLogs.map((entry) => (
                    <li key={entry.id}>
                      <span className="muted">{formatTime(entry.ts)}</span> [
                      {entry.level}] {entry.message}
                    </li>
                  ))}
                </ul>
              )}
              <button
                type="button"
                className="danger"
                disabled={
                  selectedTask.status !== 'queued' &&
                  selectedTask.status !== 'running'
                }
                onClick={() => void onCancelTask(selectedTask)}
              >
                Cancel
              </button>
            </div>
          )}
        </section>

        <section aria-labelledby="proposals-heading" className="panel">
          <h2 id="proposals-heading">Proposals</h2>
          <p>
            A proposal is never written to disk while it is pending.
            Approving a proposal writes the file inside the workspace.
            Rejecting a proposal means it can never be applied.
          </p>

          {proposals.length === 0 ? (
            <p>No proposals yet.</p>
          ) : (
            <ul className="item-list">
              {proposals.map((proposal) => (
                <li key={proposal.id}>
                  <button
                    type="button"
                    className="item-button"
                    aria-current={
                      proposal.id === selectedProposalId ? 'true' : undefined
                    }
                    onClick={() => setSelectedProposalId(proposal.id)}
                  >
                    <span className={`badge status-${proposal.status}`}>
                      {proposal.status}
                    </span>{' '}
                    <span>{proposal.relativePath}</span>{' '}
                    <span className="muted">
                      {formatTime(proposal.createdAt)}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}

          {selectedProposal && (
            <div className="detail">
              <h3>Proposal detail</h3>
              <p>
                Path: <code>{selectedProposal.relativePath}</code> · Status:{' '}
                <span className={`badge status-${selectedProposal.status}`}>
                  {selectedProposal.status}
                </span>
              </p>
              <h4>Diff</h4>
              <pre className="diff">{selectedProposal.diff}</pre>
              {selectedProposal.status === 'pending' && (
                <div className="button-row">
                  <button
                    type="button"
                    className="primary"
                    onClick={() => void decideProposal(selectedProposal, true)}
                  >
                    Approve
                  </button>
                  <button
                    type="button"
                    className="danger"
                    onClick={() => void decideProposal(selectedProposal, false)}
                  >
                    Reject
                  </button>
                </div>
              )}
              {selectedProposal.status === 'approved' && (
                <p>This proposal was approved and written inside the workspace.</p>
              )}
              {selectedProposal.status === 'rejected' && (
                <p>This proposal was rejected and can never be applied.</p>
              )}
            </div>
          )}
        </section>

        <section aria-labelledby="audit-heading" className="panel">
          <h2 id="audit-heading">Audit</h2>
          {audit.length === 0 ? (
            <p>No audit entries yet.</p>
          ) : (
            <ul className="audit-list">
              {audit.map((entry) => (
                <li key={entry.id}>
                  <span className="muted">{formatTime(entry.ts)}</span> —{' '}
                  {entry.actor} — <strong>{entry.event}</strong> —{' '}
                  {entry.detail}
                </li>
              ))}
            </ul>
          )}
        </section>
      </main>
    </div>
  );
}
