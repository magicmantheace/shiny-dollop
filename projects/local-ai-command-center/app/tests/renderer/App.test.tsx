// @vitest-environment jsdom
import './setup';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { App } from '../../src/components/App';
import { MAX_PROMPT_CHARS } from '../../shared/types';
import {
  installFakeLacc,
  sampleHealth,
  sampleProposal,
  sampleTask,
} from './fake';

describe('App', () => {
  it('renders config from configGet and the resource strip incl. unavailable GPU', async () => {
    installFakeLacc();
    render(<App />);

    expect(await screen.findByText(/Endpoint OK/)).toBeInTheDocument();
    expect(screen.getByText(/12 ms/)).toBeInTheDocument();
    expect(screen.getByText(/2 models available/)).toBeInTheDocument();

    // Config values land in the endpoint form.
    expect(screen.getByLabelText('Base URL')).toHaveValue(
      'http://127.0.0.1:11434',
    );
    expect(screen.getByLabelText('Model')).toHaveValue('llama3');
    expect(screen.getByLabelText('Timeout (ms)')).toHaveValue(15000);
    expect(screen.getByLabelText('Workspace root')).toHaveValue(
      '/workspace/demo',
    );
    expect(screen.getByLabelText('Mode')).toHaveValue('mock');

    // Resource strip.
    expect(screen.getByText(/Test CPU 3000/)).toBeInTheDocument();
    expect(screen.getByText(/8 cores/)).toBeInTheDocument();
    expect(
      screen.getByText(/4\.00 GiB free \/ 16\.00 GiB total/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        /GPU: unavailable — GPU detection is not available in this build/,
      ),
    ).toBeInTheDocument();
  });

  it('shows a free-text model input when no models are loaded', async () => {
    installFakeLacc({
      models: [],
      health: sampleHealth({ models: [] }),
    });
    render(<App />);

    expect(await screen.findByText(/Endpoint OK/)).toBeInTheDocument();
    const modelInput = screen.getByLabelText('Model');
    expect(modelInput.tagName).toBe('INPUT');
    expect(modelInput).toHaveValue('llama3');
  });

  it('health failure shows the offline banner with message and setup guidance', async () => {
    installFakeLacc({
      health: sampleHealth({
        ok: false,
        latencyMs: null,
        models: [],
        message:
          'Connection refused at http://127.0.0.1:11434 — is the runtime running?',
      }),
    });
    render(<App />);

    expect(await screen.findByText('Endpoint offline')).toBeInTheDocument();
    expect(
      screen.getByText(/Connection refused at http:\/\/127\.0\.0\.1:11434/),
    ).toBeInTheDocument();
    expect(screen.getByText(/start your local runtime/i)).toBeInTheDocument();
    expect(
      screen.getByText(/switch to Offline mock mode to explore/i),
    ).toBeInTheDocument();
  });

  it('saves the edited config via configSave', async () => {
    const fake = installFakeLacc();
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText(/Endpoint OK/);

    const baseUrl = screen.getByLabelText('Base URL');
    await user.clear(baseUrl);
    await user.type(baseUrl, 'http://127.0.0.1:1234');
    await user.click(screen.getByRole('button', { name: 'Save' }));

    expect(await screen.findByText('Configuration saved.')).toBeInTheDocument();
    expect(fake.calls).toContain('configSave');
    expect(fake.callArgs.configSave?.[0]?.[0]).toMatchObject({
      baseUrl: 'http://127.0.0.1:1234',
    });
  });

  it('Browse… fills the workspace root from pickDirectory', async () => {
    const fake = installFakeLacc();
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText(/Endpoint OK/);

    await user.click(screen.getByRole('button', { name: 'Browse…' }));

    expect(fake.calls).toContain('pickDirectory');
    expect(
      await screen.findByDisplayValue('/workspace/picked'),
    ).toBeInTheDocument();
  });

  it('submits a task: fake records tasksSubmit and the task appears', async () => {
    const fake = installFakeLacc();
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText(/Endpoint OK/);

    await user.type(
      screen.getByLabelText('Prompt'),
      'Write a haiku about snow',
    );
    expect(
      screen.getByText(
        `${'Write a haiku about snow'.length} / ${MAX_PROMPT_CHARS} characters`,
      ),
    ).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Submit' }));

    expect(fake.callArgs.tasksSubmit).toEqual([
      [{ prompt: 'Write a haiku about snow' }],
    ]);
    // The new task is auto-selected, so its detail/output is visible…
    expect(
      await screen.findByText(/Mock output for: Write a haiku about snow/),
    ).toBeInTheDocument();
    // …and it is present in the task list.
    expect(
      screen.getByRole('button', { name: /Write a haiku about snow/ }),
    ).toBeInTheDocument();
  });

  it('selecting a running task and clicking Cancel calls tasksCancel', async () => {
    const fake = installFakeLacc({
      tasks: [
        sampleTask({
          id: 'task-run',
          prompt: 'Long running job',
          status: 'running',
          output: null,
          finishedAt: null,
        }),
      ],
      logs: {
        'task-run': [
          {
            id: 'log-run',
            taskId: 'task-run',
            seq: 1,
            ts: '2026-10-23T18:01:01.000Z',
            level: 'info',
            message: 'Working on it',
          },
        ],
      },
    });
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText(/Endpoint OK/);

    await user.click(
      screen.getByRole('button', { name: /Long running job/ }),
    );
    expect(await screen.findByText(/Working on it/)).toBeInTheDocument();

    const cancel = screen.getByRole('button', { name: 'Cancel' });
    expect(cancel).toBeEnabled();
    await user.click(cancel);

    expect(fake.callArgs.tasksCancel).toEqual([['task-run']]);
    await waitFor(() => {
      expect(screen.getAllByText('cancelled').length).toBeGreaterThan(0);
    });
    expect(screen.getByRole('button', { name: 'Cancel' })).toBeDisabled();
  });

  it('rejecting a pending proposal calls proposalsReject and shows rejected status', async () => {
    const fake = installFakeLacc();
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText(/Endpoint OK/);

    await user.click(
      screen.getByRole('button', { name: /notes\/todo\.txt/ }),
    );
    expect(
      await screen.findByText(/\+hello from the model/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Rejecting a proposal means it can never be applied/),
    ).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Reject' }));

    expect(fake.callArgs.proposalsReject).toEqual([['prop-1']]);
    expect(
      await screen.findByText(
        'This proposal was rejected and can never be applied.',
      ),
    ).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Reject' })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Approve' })).toBeNull();
  });

  it('approving a pending proposal calls proposalsApprove and shows approved status', async () => {
    const fake = installFakeLacc({
      proposals: [sampleProposal({ id: 'prop-9' })],
    });
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText(/Endpoint OK/);

    await user.click(
      screen.getByRole('button', { name: /notes\/todo\.txt/ }),
    );
    await user.click(await screen.findByRole('button', { name: 'Approve' }));

    expect(fake.callArgs.proposalsApprove).toEqual([['prop-9']]);
    expect(
      await screen.findByText(
        'This proposal was approved and written inside the workspace.',
      ),
    ).toBeInTheDocument();
  });

  it('renders audit entries', async () => {
    installFakeLacc();
    render(<App />);

    expect(await screen.findByText('task.submitted')).toBeInTheDocument();
    expect(screen.getByText(/Task task-1 submitted/)).toBeInTheDocument();
    expect(screen.getByText(/user/)).toBeInTheDocument();
  });

  it('polling refreshes proposals and audit when a running task completes', async () => {
    const fake = installFakeLacc({
      tasks: [
        sampleTask({
          id: 'task-run',
          prompt: 'Generate a proposal',
          status: 'running',
          output: null,
          finishedAt: null,
        }),
      ],
      proposals: [],
      audit: [],
    });
    render(<App />);
    expect(await screen.findByText(/Endpoint OK/)).toBeInTheDocument();
    expect(screen.getByText('No proposals yet.')).toBeInTheDocument();

    // The task completes between polls and the engine creates a proposal.
    fake.state.tasks = [
      sampleTask({
        id: 'task-run',
        prompt: 'Generate a proposal',
        status: 'completed',
        output: 'done',
      }),
    ];
    fake.state.proposals = [sampleProposal()];
    const proposalsCallsBefore = fake.calls.filter(
      (c) => c === 'proposalsList',
    ).length;
    const auditCallsBefore = fake.calls.filter(
      (c) => c === 'auditList',
    ).length;

    // The poll interval is 1s of real time: the proposal must appear without
    // any manual refresh once a poll observes the completion.
    expect(
      await screen.findByRole(
        'button',
        { name: /notes\/todo\.txt/ },
        { timeout: 4000 },
      ),
    ).toBeInTheDocument();
    expect(
      fake.calls.filter((c) => c === 'proposalsList').length,
    ).toBeGreaterThan(proposalsCallsBefore);
    expect(fake.calls.filter((c) => c === 'auditList').length).toBeGreaterThan(
      auditCallsBefore,
    );
    expect(screen.queryByText('No proposals yet.')).toBeNull();
  });

  it('surfaces API {code, message} errors in the visible error area', async () => {
    installFakeLacc({
      overrides: {
        proposalsReject: async () => {
          throw {
            code: 'PROPOSAL_NOT_PENDING',
            message: 'Proposal prop-1 is already decided',
          };
        },
      },
    });
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText(/Endpoint OK/);

    await user.click(
      screen.getByRole('button', { name: /notes\/todo\.txt/ }),
    );
    await user.click(await screen.findByRole('button', { name: 'Reject' }));

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('PROPOSAL_NOT_PENDING');
    expect(alert).toHaveTextContent('Proposal prop-1 is already decided');
  });
});
